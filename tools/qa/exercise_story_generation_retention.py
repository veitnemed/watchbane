"""Synthetic A→B→C retention proof on one private TCP listener, not service routing."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import gc
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from weakref import ref

from candidates.story_semantic import LocalE5
from tools.qa import exercise_story_generation_tcp as tcp, exercise_story_shared_session as shared
from tools.qa.exercise_story_joint_cgroup import _BATCH
from tools.qa.prebuild_story_passages import prebuild, private_directory


_NAMES = ("a", "b", "c")
_WAIT = 15


def rows(name):
    if name == "a":
        return tcp.rows("old")
    if name == "b":
        return tcp.rows("new")
    if name != "c":
        raise ValueError("Expected a sealed synthetic generation name")
    movie, tv, filler = tcp.rows("new")
    return (movie | {"overview": "Альпинист оставляет горную станцию и строит зимнее укрытие.",
                     "poster_path": "/qa-c-movie.jpg"},
            tv, filler, movie | {"tmdb_id": 2147482011, "year": 2014, "title": "Дополнительный фильм",
                                 "overview": "Астроном устраивает выставку в новом музее."})


def _data(name):
    return "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                   for row in rows(name)).encode()


def prepare(directory, model):
    bundle = private_directory(directory)
    if any(bundle.iterdir()):
        raise ValueError("Expected an empty private QA directory")
    pins = {}
    old = None
    for name in _NAMES:
        generation = bundle / name
        (generation / "cache").mkdir(mode=0o700, parents=True)
        catalog = generation / "synthetic.jsonl"
        raw = _data(name)
        catalog.write_bytes(raw)
        options = {}
        if old is not None:
            options = {"previous_catalog": bundle / old / "synthetic.jsonl",
                       "previous_catalog_sha256": pins[old][0],
                       "previous_cache_dir": bundle / old / "cache",
                       "previous_snapshot_sha256": pins[old][1]}
        result = prebuild(catalog, sha256(raw).hexdigest(), model, generation / "cache",
                          batch_size=_BATCH, **options)
        if (result["rows"] != len(rows(name))
                or (old is not None and (result["reused_rows"], result["encoded_rows"]) != (len(rows(name)) - 2, 2))):
            raise ValueError("Unexpected synthetic prebuild or sealed prior reuse")
        pins[name] = [result["catalog_sha256"], result["snapshot_sha256"]]
        old = name
    with (bundle / "pins.json").open("x", encoding="ascii") as manifest:
        json.dump(pins, manifest)
    return {"synthetic_prebuilt": [2, 3, 4], "reused_from_prior": [1, 2]}


def _read_pins(directory):
    bundle = private_directory(directory)
    with (bundle / "pins.json").open("rb") as stream:
        raw = stream.read(1025)
    if len(raw) > 1024:
        raise ValueError("Invalid bounded manifest")
    pins = json.loads(raw)
    if type(pins) is not dict or set(pins) != set(_NAMES):
        raise ValueError("Invalid manifest generations")
    for name, pair in pins.items():
        if (type(pair) is not list or len(pair) != 2 or pair[0] != sha256(_data(name)).hexdigest()
                or type(pair[1]) is not str or len(pair[1]) != 64
                or any(char not in "0123456789abcdef" for char in pair[1])):
            raise ValueError("Expected the exact synthetic catalogs and prebuilt pins")
    return bundle, pins


def _artifacts(bundle):
    # All accepted catalogs and vectors are tiny exact synthetic fixtures.
    paths = [bundle / "pins.json"]
    for name in _NAMES:
        directory = bundle / name
        paths.append(directory / "synthetic.jsonl")
        files = tuple((directory / "cache/server_passage_snapshots_v1").glob("*.wbsvec"))
        if len(files) != 1:
            raise ValueError("Expected one sealed matrix per synthetic generation")
        paths.extend(files)
    fingerprint = {}
    for path in paths:
        metadata = path.stat()
        if path.is_symlink() or not path.is_file() or not 0 < metadata.st_size <= 65536:
            raise ValueError("Unexpected artifact for bounded synthetic evidence")
        with path.open("rb") as stream:
            data = stream.read(65537)
        if len(data) != metadata.st_size:
            raise ValueError("Artifact changed while reading")
        fingerprint[path] = (metadata.st_ino, len(data), sha256(data).digest())
    return fingerprint


@dataclass
class Selection:
    current: tcp.Generation
    revision: int = 0

    def switch(self, revision, generation):
        # This QA app has one event-loop routing owner. An epoch stays
        # comparable even after the expected generation's objects drained.
        if self.revision != revision:
            return False
        self.current = generation
        self.revision += 1
        return True


class Retention:
    """Count observable reference lifetimes independently from native memory."""

    def __init__(self):
        self.observed = {}
        self.peak = 0

    def live(self, name):
        return [label for label, target in self.observed[name].items() if target() is not None]

    def count(self):
        return sum(bool(self.live(name)) for name in self.observed)

    def require_staging_slot(self):
        if self.count() >= 2:
            raise ValueError("Both generation slots remain referenced; staging refused")

    def watch(self, name, generation):
        self.observed[name] = {label: ref(target) for label, target in (
            ("bundle", generation), ("engine", generation.engine),
            ("retrieval", generation.engine.retrieval), ("vectors", generation.engine.vectors),
        )}
        self.peak = max(self.peak, self.count())
        if self.peak > 2:
            raise ValueError("More than two observable resident indices")

    async def drained(self, name):
        deadline = monotonic() + 2
        while self.live(name) and monotonic() < deadline:
            gc.collect()
            await asyncio.sleep(.01)
        if self.live(name):
            raise ValueError("Drained generations still have live references")


def _verify(reply, name, ordinal):
    entries = rows(name)
    row = entries[ordinal]
    key = f"tmdb:{row['media_type']}:{row['tmdb_id']}"
    card = {k: v for k, v in row.items() if k not in ("poster_path", "tmdb_id")}
    card.update(id=key, evidence=row["overview"])
    movies = sum(item["media_type"] == "movie" for item in entries)
    if reply != {"source": "tmdb", "results": [card], "artwork": {key: row["poster_path"]},
                 "index": {"total": len(entries), "movies": movies, "tv": len(entries) - movies},
                 "outcome": {"state": "candidates", "reason": "possible_local_results"}}:
        raise ValueError("Loopback reply mixed generations")


async def rehearse(directory, model, *, model_factory=LocalE5):
    bundle, pins = _read_pins(directory)
    before = _artifacts(bundle)
    model = Path(model)
    if not (model / "onnx/model.onnx").is_file():
        raise ValueError("Expected installed pinned FP32 model")
    encoder = shared.SharedProbeEncoder(model_factory(model))
    if encoder.variant != "fp32":
        raise ValueError("Expected installed pinned FP32 model")
    retention = Retention()

    async def stage(name, *, folder=None, label=None):
        retention.require_staging_slot()
        result = await asyncio.wait_for(asyncio.to_thread(
            tcp.build_checked_generation, folder or bundle / name, pins[name], len(rows(name)), encoder,
        ), _WAIT)
        retention.watch(label or name, result)
        return result

    a = await stage("a")
    selection = Selection(a)
    held = None

    async def before_search(generation):
        nonlocal held
        if held is None:
            return
        expected, captured, resume = held
        held = None
        if expected() is not generation:
            raise ValueError("Expected exact captured bundle")
        captured.set()
        await asyncio.wait_for(resume.wait(), _WAIT)

    async with tcp.listener(tcp.app_for(selection, before_search)) as port:
        async def request(ordinal=0):
            return await asyncio.wait_for(asyncio.to_thread(tcp.post, port, shared.query_for(ordinal)), _WAIT)

        async def check(name):
            for ordinal in (0, 1):
                _verify(await request(ordinal), name, ordinal)

        @asynccontextmanager
        async def capture(generation):
            nonlocal held
            captured, resume = asyncio.Event(), asyncio.Event()
            held = (ref(generation), captured, resume)
            # Do not retain a strong function-argument reference across yield.
            del generation
            task = asyncio.create_task(request())
            try:
                await asyncio.wait_for(captured.wait(), _WAIT)
                yield task
            finally:
                resume.set()
                await task

        await check("a")
        epoch_a = selection.revision
        b = await stage("b")
        async with capture(a) as inflight_a:
            if not selection.switch(epoch_a, b):
                raise ValueError("Expected A→B compare-and-switch")
            del a
            if set(retention.live("a")) != {"bundle", "engine", "retrieval", "vectors"}:
                raise ValueError("Expected the captured request to retain A")
            try:
                await stage("c")
            except ValueError as error:
                if str(error) != "Both generation slots remain referenced; staging refused":
                    raise
            else:
                raise ValueError("Admitted a third generation before A drained")
        _verify(inflight_a.result(), "a", 0)
        await retention.drained("a")
        await check("b")

        with TemporaryDirectory(prefix="wb-retention-corrupt-") as scratch:
            damaged = shared.corrupt_copy(bundle / "c", Path(scratch), len(rows("c")))
            try:
                await stage("c", folder=damaged)
            except ValueError as error:
                if str(error) != "Strict snapshot failed exact byte verification.":
                    raise
            else:
                raise ValueError("Corrupted C passed strict preparation")
        await check("b")
        epoch_b = selection.revision
        c = await stage("c")
        async with capture(b) as inflight_b:
            if selection.switch(epoch_a, c) or not selection.switch(epoch_b, c):
                raise ValueError("C accepted a stale receipt or refused its fresh one")
        _verify(inflight_b.result(), "b", 0)
        await check("c")
        if not selection.switch(selection.revision, b) or selection.switch(epoch_b, c):
            raise ValueError("C→B rollback or stale ABA test failed")
        del c
        await retention.drained("c")
        await check("b")

        begin = monotonic()
        reloaded_a = await stage("a", label="a_reloaded")
        reload_ms = round((monotonic() - begin) * 1000, 3)
        if selection.current is not b or reloaded_a.index["total"] != 2 or retention.count() != 2:
            raise ValueError("Read-only A reload changed the active B generation")
        await check("b")
        del reloaded_a
        await retention.drained("a_reloaded")

    if before != _artifacts(bundle) or encoder.forbidden_startup_calls:
        raise ValueError("Sealed artifacts were modified or a passage re-encode occurred")
    return {"synthetic_only": True, "one_tcp_listener": True, "verified_model_sessions": 1,
            "old_a_captured_then_drained_before_c": True, "premature_c_refused": True,
            "corrupted_c_refused": True, "stale_c_refused_before_activation_and_after_rollback": True,
            "old_b_payload_coherent_after_c": True, "rollback_c_to_b": True,
            "observed_peak_live_generation_refs": retention.peak, "weakrefs_not_memory_measurement": True,
            "sealed_a_reload_while_b_active_ms": reload_ms, "artifacts_unchanged": True,
            "rows": [2, 3, 4], "query_encodes": encoder.query_calls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "rehearse"))
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    args = parser.parse_args()
    result = (prepare(args.bundle_dir, args.model_dir) if args.phase == "prepare"
              else asyncio.run(rehearse(args.bundle_dir, args.model_dir)))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
