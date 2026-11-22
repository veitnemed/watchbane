"""Synthetic-only loopback QA: one verified E5 session, two strict generations.

The probe starts a private IPv4 TCP listener and never swaps product server
state. Controlled barriers demonstrate generation consistency, not uptime.
"""

import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from hashlib import sha256
from http.client import HTTPConnection
import json
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from threading import Event, Lock
from time import monotonic
from types import MappingProxyType

from candidates.story_artwork import is_provider_poster_path
from candidates.story_semantic import LocalE5
from tools.qa import exercise_story_shared_session as shared
from tools.qa.exercise_story_joint_cgroup import _BATCH, fixture
from tools.qa.prebuild_story_passages import prebuild, private_directory
from web import story_api


_OLD, _NEW = "old", "new"
_NAMES = (_OLD, _NEW)
_HEADERS = ("Watchbane-Search-Outcome", "Watchbane-Search-Artwork", "Watchbane-Search-Index")
_WAIT = 15
_CAP = 32 * 1024


def rows(name):
    movie, tv = fixture(name)
    entries = (movie | {"poster_path": f"/qa-{name}-movie.jpg"},
               tv | {"poster_path": "/qa-invariant-tv.png"})
    # Differing total and typed TV counts expose mixed-generation metadata.
    if name == _NEW:
        entries += (tv | {"tmdb_id": 2147482010, "year": 2012, "title": "Дополнительная фикстура"},)
    return entries


def data(name):
    return "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows(name)).encode()


def prepare(directory, model):
    bundle = private_directory(directory)
    if any(bundle.iterdir()):
        raise ValueError("Expected an empty private QA directory")
    pins = {}
    for name in _NAMES:
        folder = bundle / name
        (folder / "cache").mkdir(mode=0o700, parents=True)
        catalog = folder / "synthetic.jsonl"
        raw = data(name)
        catalog.write_bytes(raw)
        result = prebuild(catalog, sha256(raw).hexdigest(), model, folder / "cache", batch_size=_BATCH)
        if result["rows"] != len(rows(name)):
            raise ValueError("Synthetic generation row count changed")
        pins[name] = [result["catalog_sha256"], result["snapshot_sha256"]]
    (bundle / "pins.json").write_text(json.dumps(pins), encoding="ascii")
    return {"prepared_synthetic_generations": 2, "rows": [2, 3]}


def read_pins(directory):
    bundle = private_directory(directory)
    with (bundle / "pins.json").open("rb") as stream:
        raw = stream.read(1025)
    if len(raw) > 1024:
        raise ValueError("Invalid bounded pins")
    pins = json.loads(raw)
    if type(pins) is not dict or set(pins) != set(_NAMES):
        raise ValueError("Invalid pins map")
    for name in _NAMES:
        pair = pins[name]
        if (type(pair) is not list or len(pair) != 2 or pair[0] != sha256(data(name)).hexdigest()
                or type(pair[1]) is not str or len(pair[1]) != 64
                or any(c not in "0123456789abcdef" for c in pair[1])):
            raise ValueError("Expected the exact synthetic catalog and prebuilt snapshot pin")
    return bundle, pins


@dataclass(frozen=True)
class Generation:
    engine: object
    artwork: MappingProxyType
    index: MappingProxyType


def build(folder, pins, name, encoder, *, barrier=None):
    engine = shared.build(folder, pins, len(rows(name)), encoder, verified_callback=barrier)
    artwork = {}
    documents, digest = story_api._load_documents(folder / "synthetic.jsonl", artwork_paths=artwork)
    index = story_api._index_counts(engine)
    if digest != pins[0] or tuple(documents) != engine.documents or index is None:
        raise ValueError("Generation metadata failed exact verification")
    if not artwork.keys() <= {doc.key for doc in documents} or not all(
            is_provider_poster_path(path) for path in artwork.values()):
        raise ValueError("Generation artwork failed typed verification")
    return Generation(engine, MappingProxyType(dict(artwork)), MappingProxyType(dict(index)))


class Selection:
    def __init__(self, generation):
        self.current = generation

    def switch(self, expected, generation):
        # All references are written on the sole event loop. Cross-thread
        # operators and a durable/distributed routing pointer are out of scope.
        if self.current is not expected:
            return False
        self.current = generation
        return True


def app_for(selection, before_search):
    from fastapi import FastAPI, HTTPException, Request
    from starlette.concurrency import run_in_threadpool

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    gate = Lock()

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = ", ".join(_HEADERS)
        return response

    @app.post("/v1/search")
    async def search(request: Request):
        if request.client is None or request.client.host != "127.0.0.1":
            raise HTTPException(403, "loopback_only")
        if any(request.headers.getlist(name) != ["1"] for name in _HEADERS):
            raise HTTPException(400, "required_qa_protocol_version")
        query, limit = await story_api._read_query(request)
        if not gate.acquire(blocking=False):
            raise HTTPException(503, "search_busy", headers={"Retry-After": "1"})
        try:
            # Capture every generation-varying dependency before any await.
            generation = selection.current
            await before_search(generation)
            result = await run_in_threadpool(generation.engine.search_with_outcome, query, limit=limit)
            cards = [{
                "id": hit.document.key, "title": hit.document.title, "year": hit.document.year,
                "media_type": hit.document.media_type, "overview": hit.document.overview,
                "evidence": hit.evidence, "language": "ru-RU",
            } for hit in result.hits]
            from fastapi.responses import JSONResponse
            return JSONResponse({
                "source": "tmdb", "results": cards, "outcome": story_api._search_outcome(result),
                "artwork": {card["id"]: generation.artwork[card["id"]]
                            for card in cards if card["id"] in generation.artwork},
                "index": dict(generation.index),
            }, headers=dict.fromkeys(_HEADERS, "1"))
        except Exception:
            raise HTTPException(503, "search_unavailable") from None
        finally:
            gate.release()

    return app


def post(port, query, *, expected_status=200):
    conn = HTTPConnection("127.0.0.1", port, timeout=_WAIT)
    try:
        headers = dict.fromkeys(_HEADERS, "1") | {"Content-Type": "application/json"}
        body = json.dumps({"query": query, "limit": 1}, ensure_ascii=False).encode()
        conn.request("POST", "/v1/search", body, headers=headers)
        response = conn.getresponse()
        payload = response.read(_CAP + 1)
        if (response.status != expected_status or len(payload) > _CAP
                or response.getheader("Cache-Control") != "no-store"):
            raise ValueError("Unexpected bounded local HTTP reply")
        if expected_status == 200 and any(response.getheader(name) != "1" for name in _HEADERS):
            raise ValueError("Missing exact protocol echo")
        if expected_status == 503 and (response.getheader("Retry-After") != "1"
                or any(response.getheader(name) is not None for name in _HEADERS)):
            raise ValueError("Unexpected busy contract")
        return json.loads(payload)
    finally:
        conn.close()


def verify(reply, generation, ordinal):
    raw_row = rows(generation)[ordinal]
    key = f"tmdb:{raw_row['media_type']}:{raw_row['tmdb_id']}"
    card = {k:v for k,v in raw_row.items() if k not in {"tmdb_id", "poster_path"}}
    card.update(id=key, evidence=raw_row["overview"])
    if reply != {"source": "tmdb", "results": [card],
                 "artwork": {key: raw_row["poster_path"]},
                 "index": {"total": len(rows(generation)), "movies": 1, "tv": len(rows(generation)) - 1},
                 "outcome": {"state": "candidates", "reason": "possible_local_results"}}:
        raise ValueError("Response mixed generations or changed its negotiated contract")


@asynccontextmanager
async def listener(app):
    import uvicorn

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, access_log=False, proxy_headers=False, log_level="error"))
        running = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            deadline = monotonic() + _WAIT
            while not server.started and not running.done() and monotonic() < deadline:
                await asyncio.sleep(.01)
            if not server.started:
                raise RuntimeError("Private loopback listener did not start")
            yield sock.getsockname()[1]
        finally:
            server.should_exit = True
            await asyncio.wait_for(running, _WAIT)


async def rehearse(directory, model, *, model_factory=LocalE5):
    bundle, pins = read_pins(directory)
    model = Path(model)
    if not (model / "onnx/model.onnx").is_file():
        raise ValueError("Expected local portable FP32 weights")
    encoder = shared.SharedProbeEncoder(model_factory(model))
    if encoder.variant != "fp32":
        raise ValueError("Expected one pinned FP32 model")
    old = await asyncio.wait_for(asyncio.to_thread(build, bundle / _OLD, pins[_OLD], _OLD, encoder), _WAIT)
    selection = Selection(old)
    capture, release = asyncio.Event(), asyncio.Event()
    hold_one = False

    async def before_search(generation):
        nonlocal hold_one
        if hold_one:
            hold_one = False
            if generation is not old:
                raise ValueError("Expected the old in-flight capture")
            capture.set()
            await asyncio.wait_for(release.wait(), _WAIT)

    async with listener(app_for(selection, before_search)) as port:
        async def request(index, **kwargs):
            return await asyncio.wait_for(asyncio.to_thread(post, port, shared.query_for(index), **kwargs), _WAIT)

        async def check(name):
            for i in range(2):
                verify(await request(i), name, i)

        await check(_OLD)
        with TemporaryDirectory(prefix="wb-tcp-candidate-") as scratch:
            corrupted = shared.corrupt_copy(bundle / _NEW, Path(scratch), len(rows(_NEW)))
            try:
                await asyncio.wait_for(asyncio.to_thread(build, corrupted, pins[_NEW], _NEW, encoder), _WAIT)
            except ValueError as error:
                if str(error) != "Strict snapshot failed exact byte verification.":
                    raise
            else:
                raise ValueError("Candidate with a bad vector payload was accepted")
        await check(_OLD)

        # No barrier here. Record what actually happened without requiring
        # overlap on this tiny fixture or extrapolating to live availability.
        started = monotonic()
        unpaused = asyncio.create_task(asyncio.to_thread(build, bundle / _NEW, pins[_NEW], _NEW, encoder))
        verify(await request(0), _OLD, 0)
        unpaused_pending_at_reply = not unpaused.done()
        await asyncio.wait_for(unpaused, _WAIT)
        unpaused_ms = round((monotonic() - started) * 1000, 3)
        del unpaused

        verified, resume = Event(), Event()

        def barrier():
            verified.set()
            if not resume.wait(_WAIT):
                raise TimeoutError("Controlled staging deadline")

        staging = asyncio.create_task(asyncio.to_thread(build, bundle / _NEW, pins[_NEW], _NEW, encoder,
                                                        barrier=barrier))
        try:
            if not await asyncio.to_thread(verified.wait, _WAIT):
                raise TimeoutError("New candidate did not reach strict staging barrier")
            await check(_OLD)
            if staging.done():
                raise ValueError("Expected staging to still be paused")
        finally:
            resume.set()
        new = await asyncio.wait_for(staging, _WAIT)
        if (old.engine is new.engine or old.engine.vectors is new.engine.vectors
                or old.engine.encoder.encoder is not new.engine.encoder.encoder):
            raise ValueError("Expected separate indices and one shared E5 session")

        hold_one = True
        inflight = asyncio.create_task(request(0))
        try:
            await asyncio.wait_for(capture.wait(), _WAIT)
            if not selection.switch(old, new) or selection.switch(old, old):
                raise ValueError("Generation compare-and-switch did not fence stale activation")
            if await request(0, expected_status=503) != {"detail": "search_busy"}:
                raise ValueError("Unexpected body while another search owns admission")
        finally:
            release.set()
        verify(await inflight, _OLD, 0)
        await check(_NEW)
        if not selection.switch(new, old):
            raise ValueError("Rollback must compare against the exact active generation")
        await check(_OLD)
    if encoder.forbidden_startup_calls:
        raise ValueError("Strict generation staging attempted to re-encode passages")
    return {"synthetic_only": True, "one_tcp_listener": True, "verified_model_sessions": 1,
            "strict_artwork_index_outcome": True, "rows": [2, 3], "corruption_refused": True,
            "controlled_staging_old_ready": True, "stale_capture_old": True, "inflight_busy": True,
            "rollback": True, "actual_query_calls": encoder.query_calls, "forbidden_startup_encodes": 0,
            "unpaused_stage_and_old_reply_total_ms": unpaused_ms,
            "unpaused_stage_pending_when_old_reply_finished": unpaused_pending_at_reply}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "rehearse"))
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    args = parser.parse_args()
    result = (prepare(args.bundle_dir, args.model_dir) if args.phase == "prepare"
              else asyncio.run(rehearse(args.bundle_dir, args.model_dir)))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
