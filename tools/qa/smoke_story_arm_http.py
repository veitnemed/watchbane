"""E5 + Russian HTTP smoke on an explicitly SYNTHETIC one-row fixture."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import tempfile

from candidates.story_model_probe import check_model
from tools.qa.exercise_story_handover import launch, request, wait_health


# Test-only typed identity for this disposable fixture, not a lookup or a title
# acquired from TMDb. The smoke does not measure real-catalog search quality.
_FIXTURE_ID = 2147483001
_FIXTURE_TITLE = "Синтетический тайтл ARM QA"
_OVERVIEW = "Врач работает в больнице и спасает пациента."


def _cache_fingerprint(cache_dir):
    snapshots = list((cache_dir / "server_passage_snapshots_v1").iterdir())
    if len(snapshots) != 1 or snapshots[0].suffix != ".wbsvec" or not snapshots[0].is_file():
        raise RuntimeError("expected exactly one persisted passage snapshot")
    path = snapshots[0]
    stat = path.stat()
    if not 0 < stat.st_size <= 4096:  # One FP32 vector + bounded header.
        raise RuntimeError("unexpected one-row snapshot size")
    return path.name, stat.st_ino, stat.st_mtime_ns, sha256(path.read_bytes()).hexdigest()


def smoke(model_dir, *, require_native_arm=False, cache_restart=False):
    machine, system = platform.machine(), platform.system()
    if require_native_arm and (machine != "aarch64" or system != "Linux"):
        raise RuntimeError("This gate requires native Linux ARM64")
    inference = check_model(model_dir)
    if (inference.get("status") != "ok" or inference.get("variant") != "fp32"
            or inference.get("embedding_size") != 384):
        raise RuntimeError(f"Pinned FP32 inference check failed: {inference.get('status', 'unknown')}")
    with tempfile.TemporaryDirectory(prefix="watchbane-arm-smoke-") as directory:
        catalog = Path(directory) / "synthetic-qa-only.jsonl"
        row = {"tmdb_id": _FIXTURE_ID, "media_type": "movie", "title": _FIXTURE_TITLE,
               "overview": _OVERVIEW, "language": "ru-RU", "year": 2020}
        catalog.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        expected = {"source": "tmdb", "results": [dict(
            id=f"tmdb:movie:{_FIXTURE_ID}", media_type="movie", title=_FIXTURE_TITLE,
            overview=_OVERVIEW, evidence=_OVERVIEW, language="ru-RU", year=2020,
        )]}
        query = json.dumps({"query": "врач спасает пациента", "limit": 1}, ensure_ascii=False).encode("utf-8")

        def probe(**options):
            with launch(catalog, model_dir, 4, **options) as server:
                readiness = wait_health(server, 60)
                result = request(server[0], "/v1/search", query)
                if result != expected or server[1].poll() is not None:
                    raise RuntimeError("Synthetic Russian HTTP result differs from expected contract")
            return readiness, result

        restart = {}
        if cache_restart:
            cache_dir = Path(directory) / "application-cache"
            readiness, result = probe(cache_dir=cache_dir)
            persisted = _cache_fingerprint(cache_dir)
            warm_readiness, warm_result = probe(cache_dir=cache_dir)
            if warm_result != result or persisted != _cache_fingerprint(cache_dir):
                raise RuntimeError("Restart changed the HTTP result or rewrote the persisted passage snapshot")
            restart = {"warm_readiness_seconds": round(warm_readiness, 3),
                       "persisted_passage_snapshot_unchanged": True, "identical_restart_response": True}
        else:
            readiness, _ = probe()
    return {"system": system, "machine": machine, "native_arm_gate": require_native_arm,
            "fixture": "synthetic_qa_only", "e5_fp32": True, "russian_http": True,
            "readiness_seconds": round(readiness, 3), **restart}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-native-arm", action="store_true")
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--cache-restart", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(smoke(args.model_dir, require_native_arm=args.require_native_arm,
                           cache_restart=args.cache_restart)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
