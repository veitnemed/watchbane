"""Synthetic direct-ASGI QA without an HTTP listener: stage two strict generations with one E5 session."""
import argparse
import asyncio
from contextvars import ContextVar
from itertools import islice
import json
import os
from pathlib import Path
import platform
import stat
import sys
from tempfile import TemporaryDirectory
from threading import Event
import time

from candidates.story_semantic import LocalE5, SemanticStorySearch
from tools.qa.exercise_story_joint_cgroup import _BATCH, _NUMBER, _ROW_COUNTS, fixture, validated_bundle
from tools.qa.smoke_story_arm_cgroup import ROOT, read_limits, read_usage
from web import story_api
from web.story_retrieval_index import PreparedRetrievalIndex
from web.story_vector_snapshot import PassageVectorSnapshot


_WAIT = 15
_ASGI_RESPONSE_LIMIT = 32 * 1024
_BUILDING = ContextVar("building_shared_passages", default=False)


class SharedProbeEncoder:
    def __init__(self, model):
        self.model = model
        self.variant = model.variant
        self.cache_identity = model.cache_identity
        self.forbidden_startup_calls = 0
        self.query_calls = 0

    def encode(self, texts, prefix="passage: ", **kwargs):
        if _BUILDING.get():
            self.forbidden_startup_calls += 1
            raise ValueError("Passage re-encoding was attempted during strict staging.")
        if prefix == "query: ":
            self.query_calls += 1
        return self.model.encode(texts, prefix=prefix, **kwargs)


class CapturedSnapshot:
    def __init__(self, identity, verified):
        self.identity = identity
        self.verified = verified

    def load_with_digest(self, identity):
        if identity != self.identity:
            raise ValueError("Unexpected strict snapshot identity.")
        return self.verified


def build(folder, pins, rows, encoder, *, verified_callback=None):
    """Run the canonical strict initial wrapper against one already audited matrix."""
    catalog_pin, snapshot_pin = pins
    documents, actual = story_api._load_documents(folder / "synthetic.jsonl")
    if actual != catalog_pin or len(documents) != rows:
        raise ValueError("Strict catalog does not match exact synthetic scope.")
    identity = story_api._startup_passage_identity(catalog_pin, encoder, documents, _BATCH)
    verified = PassageVectorSnapshot(folder / "cache").load_with_digest(identity)
    if verified is None or verified[1] != snapshot_pin:
        raise ValueError("Strict snapshot failed exact byte verification.")
    if verified_callback is not None:
        verified_callback()
    wrapper = story_api._StartupPassageEncoder(
        encoder, CapturedSnapshot(identity, verified), identity, documents,
        startup_batch_size=_BATCH, expected_snapshot_sha256=snapshot_pin)
    token = _BUILDING.set(True)
    try:
        engine = SemanticStorySearch(documents, wrapper, retrieval_factory=PreparedRetrievalIndex)
    finally:
        _BUILDING.reset(token)
    if engine.vectors is not verified[0]:
        raise ValueError("The staged engine did not consume its exact audited matrix.")
    # Keep the canonical matrix in the engine, not an extra reference through
    # the temporary strict startup adapter after successful construction.
    wrapper.cache = None
    return engine


async def asgi_post(app, query):
    """Direct ASGI transport: actual route/middleware, no HTTP listening socket."""
    raw = json.dumps({"query": query, "limit": 1}, ensure_ascii=False).encode("utf-8")
    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
             "http_version": "1.1", "method": "POST", "scheme": "http", "path": "/v1/search",
             "root_path": "", "query_string": b"", "headers": [(b"content-type", b"application/json")]}
    delivered = False
    pending = asyncio.Event()
    status = None
    cache_control = []
    response = bytearray()

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": raw, "more_body": False}
        await pending.wait()
        return {"type": "http.disconnect"}

    async def send(event):
        nonlocal status, cache_control
        if event["type"] == "http.response.start":
            status = event["status"]
            cache_control = [value for key,value in event["headers"] if key == b"cache-control"]
        elif event["type"] == "http.response.body":
            part = event.get("body", b"")
            if len(response) + len(part) > _ASGI_RESPONSE_LIMIT:
                raise ValueError("Synthetic response exceeded QA byte cap.")
            response.extend(part)

    await asyncio.wait_for(app(scope, receive, send), _WAIT)
    if status != 200 or cache_control != [b"no-store"]:
        raise ValueError("Unexpected local ASGI search response.")
    return json.loads(response)


def query_for(index):
    # Reserved years isolate the typed probes, not the ranking quality.
    return ("фильм 2000 про альпиниста и горную станцию", "сериал 2010 про доктора в больнице")[index]


def expected_generation(generation, index):
    row = fixture(generation)[index]
    expected = {key: value for key, value in row.items() if key != "tmdb_id"}
    expected.update(id=f"tmdb:{row['media_type']}:{_NUMBER}", evidence=row["overview"])
    return {"source": "tmdb", "results": [expected]}


async def check_generation(app, name):
    for index in range(2):
        result = await asgi_post(app, query_for(index))
        if result != expected_generation(name, index):
            raise ValueError("Typed marker or unaffected TV response differs.")


def corrupt_copy(source, scratch, rows):
    """Bounded detached fixture copy; original bundle is always left untouched."""
    folder = scratch / "invalid"
    (folder / "cache/server_passage_snapshots_v1").mkdir(parents=True)
    # The identity namespace may have only the sealed prebuild from prepare.
    namespace = source / "cache/server_passage_snapshots_v1"
    if namespace.is_symlink():
        raise ValueError("Expected a real synthetic cache namespace.")
    originals = tuple(islice(namespace.iterdir(), 2))
    if len(originals) != 1 or not stat.S_ISREG(originals[0].lstat().st_mode):
        raise ValueError("Expected one regular synthetic prebuilt snapshot.")
    with originals[0].open("rb") as file:
        raw = bytearray(file.read(81 + rows * 384 * 4))
    if len(raw) != 80 + rows * 384 * 4:
        raise ValueError("Unexpected synthetic prebuilt size.")
    raw[-1] ^= 1
    (folder / "cache/server_passage_snapshots_v1" / originals[0].name).write_bytes(raw)
    catalog_path = source / "synthetic.jsonl"
    if not stat.S_ISREG(catalog_path.lstat().st_mode):
        raise ValueError("Expected a regular synthetic catalog.")
    with catalog_path.open("rb") as file:
        catalog = file.read(1024 * 1024 + 1)
    if len(catalog) > 1024 * 1024:
        raise ValueError("Synthetic catalog exceeds scratch cap.")
    (folder / "synthetic.jsonl").write_bytes(catalog)
    return folder


async def rehearse(bundle, model_dir, pins, rows, report, *, sample_memory=None, model_factory=LocalE5):
    model_dir = Path(model_dir)
    if not (model_dir / "onnx/model.onnx").is_file():
        raise ValueError("Verified local FP32 weights are required.")
    encoder = SharedProbeEncoder(model_factory(model_dir))
    if encoder.variant != "fp32":
        raise ValueError("Verified local FP32 weights are required.")
    report["verified_model_sessions"] = 1
    started = time.monotonic()
    old = await asyncio.wait_for(asyncio.to_thread(build, bundle / "old", pins["old"], rows, encoder), _WAIT)
    report["old_staging_ms"] = round((time.monotonic() - started) * 1000, 3)
    app = story_api.create_app(bundle / "old/synthetic.jsonl", model_dir, engine_factory=lambda *_: old)
    async with app.router.lifespan_context(app):
        await check_generation(app, "old")
        if sample_memory is not None:
            report["old_only_memory_current_bytes"] = sample_memory()

        # Reject the corrupted detached candidate while the approved old route
        # is still selected. This generates no new model session or rebuild.
        with TemporaryDirectory(prefix="watchbane-shared-synthetic-") as scratch:
            invalid = corrupt_copy(bundle / "new", Path(scratch), rows)
            try:
                await asyncio.wait_for(asyncio.to_thread(build, invalid, pins["new"], rows, encoder), _WAIT)
            except ValueError as error:
                if str(error) != "Strict snapshot failed exact byte verification.":
                    raise
            else:
                raise ValueError("Tampered candidate was accepted.")
        if app.state.engine is not old:
            raise ValueError("Rejected staging changed the active generation.")
        await check_generation(app, "old")
        report["tampered_candidate_refused_and_old_unchanged"] = True

        verified, continue_stage = Event(), Event()

        def verify_and_pause():
            verified.set()
            if not continue_stage.wait(_WAIT):
                raise TimeoutError("Staging barrier deadline.")

        start_stage = time.monotonic()
        stage = asyncio.create_task(asyncio.to_thread(build, bundle / "new", pins["new"], rows, encoder,
                                                       verified_callback=verify_and_pause))
        try:
            if not await asyncio.to_thread(verified.wait, _WAIT):
                raise TimeoutError("Candidate verification deadline.")
            await check_generation(app, "old")
            if app.state.engine is not old or stage.done():
                raise ValueError("Old response did not overlap independently staged candidate.")
            report["old_verified_during_controlled_staging"] = True
        finally:
            continue_stage.set()
        new = await asyncio.wait_for(stage, _WAIT)
        report["new_staging_with_controlled_overlap_ms"] = round((time.monotonic() - start_stage) * 1000, 3)
        if old is new or old.vectors is new.vectors or old.encoder.encoder is not new.encoder.encoder:
            raise ValueError("Expected distinct engines sharing exactly one model session.")
        report["both_verified_indices_live_one_model_session"] = True
        if sample_memory is not None:
            report["dual_indices_memory_current_bytes"] = sample_memory()

        # The actual handler captures its engine before submitting the search.
        # Pause one captured old request; then swap, release, and prove it
        # returns old while subsequent requests use the new active reference.
        captured, complete = Event(), Event()
        old_search = old.search

        def hold_old(query, **kwargs):
            captured.set()
            if not complete.wait(_WAIT):
                raise TimeoutError("In-flight request barrier deadline.")
            return old_search(query, **kwargs)

        old.search = hold_old
        request = asyncio.create_task(asgi_post(app, query_for(0)))
        try:
            if not await asyncio.to_thread(captured.wait, _WAIT) or request.done():
                raise TimeoutError("In-flight routing witness deadline.")
            app.state.engine = new
        finally:
            complete.set()
        try:
            if await request != expected_generation("old", 0):
                raise ValueError("Captured old request crossed the generation switch.")
        finally:
            old.search = old_search
        report["inflight_old_request_preserved"] = True
        await check_generation(app, "new")
        app.state.engine = old
        await check_generation(app, "old")
        report["changed_marker_and_unchanged_tv_rollback"] = True

    report["forbidden_startup_encodes"] = encoder.forbidden_startup_calls
    report["actual_query_calls"] = encoder.query_calls


def run(bundle, model_dir, *, rows, capped, root=ROOT):
    bundle, pins = validated_bundle(bundle, rows)
    report = {"synthetic_only": True, "rows_per_generation": rows,
              "shared_cgroup_enforced": capped, "transport": "direct_asgi_no_http_listener"}
    sample = None
    if capped:
        if ((platform.system(), platform.machine(), sys.version_info[:3]) != ("Linux", "aarch64", (3, 12, 16))
                or os.geteuid() == 0 or Path("/proc/self/cgroup").read_text().strip() != "0::/"):
            raise ValueError("Native ARM64 pinned Python and one private root cgroup required.")
        report["limits"] = read_limits(root)
        usage = read_usage(root)
        if not usage["within_limit_without_oom"] or usage["memory_max_events"]:
            raise ValueError("Expected a fresh cgroup without prior limit events.")

        def sample():
            return int((root / "memory.current").read_text())
    try:
        asyncio.run(rehearse(bundle, model_dir, pins, rows, report, sample_memory=sample))
    except TimeoutError:
        report["failure"] = "controlled_handover_deadline"
    except (OSError, ValueError, RuntimeError):
        report["failure"] = "strict_or_route_verification"
    finally:
        if capped:
            report["usage"] = usage = read_usage(root)
            if any(usage[key] for key in ("oom", "oom_kill", "oom_group_kill")):
                report["resource_failure"] = "oom_event"
            elif not usage["within_limit_without_oom"] or usage["memory_max_events"]:
                report["resource_failure"] = "memory_limit_event"
    report["passed"] = bool(report.get("changed_marker_and_unchanged_tv_rollback")
                            and report.get("forbidden_startup_encodes") == 0
                            and not report.get("failure") and not report.get("resource_failure"))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
        epilog="Use the separately prepared immutable joint QA bundle; enforce a 90s host wall and inspect OOM.")
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--rows", type=int, choices=_ROW_COUNTS, default=2)
    cap = parser.add_mutually_exclusive_group(required=True)
    cap.add_argument("--require-native-arm-cgroup", action="store_true")
    cap.add_argument("--unbounded-local-development", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run(args.bundle_dir, args.model_dir, rows=args.rows, capped=args.require_native_arm_cgroup)
    except (OSError, RuntimeError, ValueError):
        print("Shared-session QA refused before completing its local verification.", file=sys.stderr)
        return 1
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
