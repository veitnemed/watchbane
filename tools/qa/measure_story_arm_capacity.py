"""Offline lab: one fresh ARM64 cgroup per synthetic E5 HTTP configuration."""
import argparse
from hashlib import sha256
import json
from math import ceil, isfinite
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
import time

from tools.qa.exercise_story_handover import launch, request, wait_health
from tools.qa.smoke_story_arm_cgroup import ROOT, read_limits, read_usage


_ROWS = (1000, 2000)
_DENSITIES = ("low", "high")
_MODES = ("baseline", "prepared")
_CACHE_PHASES = ("cold", "restart")
_REPEATS = 4
_QUERIES = ("летописец картограф", "межзвёздный полёт", "меткаааб", "летаписец")


def fixture(path, rows, density):
    from tools.qa.measure_story_lexical_capacity import make_documents
    expected = set()
    probes = []
    with path.open("x", encoding="utf-8", newline="\n") as file:
        for index, doc in enumerate(make_documents(rows, density)):
            # Shared numeric IDs across adjacent synthetic film/series rows
            # make losing the type observable. The IDs are not looked up.
            identifier = 2147482000 + index // 2
            media_type = ("movie", "tv")[index % 2]
            expected.add((media_type, f"tmdb:{media_type}:{identifier}"))
            file.write(json.dumps({"tmdb_id": identifier, "media_type": media_type,
                                   "title": doc.title, "overview": doc.overview,
                                   "language": "ru-RU", "year": 2020},
                                  ensure_ascii=False, separators=(",", ":")) + "\n")
            if index in {0, rows // 2, rows - 1}:
                probes.append(doc.overview)
    return expected, (*_QUERIES, *probes)


def ids(result, expected):
    if (not isinstance(result, dict) or result.get("source") != "tmdb"
            or not isinstance(result.get("results"), list) or len(result["results"]) != 5):
        raise RuntimeError("unexpected synthetic search result shape")
    keyed = [(row.get("media_type"), row.get("id")) for row in result["results"]]
    if len(set(keyed)) != len(keyed) or not set(keyed) <= expected:
        raise RuntimeError("unexpected typed ID in synthetic search result")
    return tuple(keyed)


def measure(model_dir, rows, density, mode, *, readiness_timeout=300, cache_dir=None, cache_phase=None):
    if mode not in _MODES or not (model_dir / "onnx/model.onnx").is_file():
        # LocalE5 verifies the official pinned files and invokes real ONNX;
        # fail here rather than silently choosing its alternate INT8 variant.
        raise RuntimeError("expected mode and pinned FP32 weights")
    if cache_phase not in (None, *_CACHE_PHASES) or (cache_dir is None) != (cache_phase is None):
        raise ValueError("cache phase and detached cache directory must be supplied together")
    if cache_phase == "cold" and any(cache_dir.iterdir()):
        raise ValueError("cold capacity probe requires an empty cache directory")
    with tempfile.TemporaryDirectory(prefix="watchbane-capacity-") as work:
        catalog = Path(work) / "synthetic-qa-only.jsonl"
        expected, queries = fixture(catalog, rows, density)
        catalog_sha256 = sha256(catalog.read_bytes()).hexdigest()
        warm = []
        bodies = [json.dumps({"query": query, "limit": 5}, ensure_ascii=False).encode("utf-8")
                  for query in queries]
        proof = Path(work) / "startup-cache-proof" if cache_phase == "restart" else None
        started = time.monotonic()
        with launch(catalog, model_dir, 4, prepared_index=mode == "prepared",
                    cache_dir=cache_dir, cache_proof=proof) as server:
            wait_health(server, readiness_timeout)
            readiness = time.monotonic() - started
            runs = []
            for iteration in range(_REPEATS):
                for index, body in enumerate(bodies):
                    start = time.monotonic()
                    result = ids(request(server[0], "/v1/search", body), expected)
                    elapsed = (time.monotonic() - start) * 1000
                    if iteration == 0:
                        runs.append((result, elapsed))
                    else:
                        if runs[index][0] != result:
                            raise RuntimeError("typed order drift on repeating synthetic query")
                        warm.append(elapsed)
            cache = {}
            if cache_phase is not None:
                identity, digest = cache_fingerprint(cache_dir, rows)
                if proof is not None and proof.read_text() != identity:
                    raise RuntimeError("restart did not consume the exact cache identity")
                cache = {"cache_phase": cache_phase, "passage_snapshot_id": identity,
                         "passage_snapshot_sha256": digest, "proof_of_cache_hit": proof is not None}
            if server[1].poll() is not None:
                raise RuntimeError("search server stopped during capacity probe")
    return {"fixture": "synthetic_qa_only", "rows": rows, "density": density, "mode": mode,
            "catalog_sha256": catalog_sha256,
            "process_ready_seconds": readiness, "first_http_ms": runs[0][1],
            "warm_samples": len(warm),
            "warm_p50_ms": percentile(warm, 0.5), "warm_p95_ms": percentile(warm, 0.95),
            "ordered_typed_results": [result for result, _ in runs], **cache}


def cache_fingerprint(cache_dir, rows):
    snapshots = list((cache_dir / "server_passage_snapshots_v1").iterdir())
    if len(snapshots) != 1 or not re.fullmatch(r"[0-9a-f]{64}\.wbsvec", snapshots[0].name):
        raise RuntimeError("expected exactly one content-addressed snapshot")
    snapshot = snapshots[0]
    # v1 header is <8s32sII32s (80 bytes), payload is 384 little-endian f32
    # elements per typed row. The real loader verifies the header and payload.
    limit = 80 + rows * 384 * 4
    with snapshot.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) != limit:
        raise RuntimeError("unexpected passage snapshot size")
    return snapshot.stem, sha256(data).hexdigest()


def percentile(values, fraction):
    return sorted(values)[ceil(len(values) * fraction) - 1]


def run(model_dir, rows, density, mode, *, root=ROOT, cache_dir=None, cache_phase=None):
    if (platform.system(), platform.machine(), sys.version_info[:3]) != ("Linux", "aarch64", (3, 12, 16)):
        raise RuntimeError("requires native Linux ARM64 and pinned Python 3.12.16")
    if os.geteuid() == 0:
        raise RuntimeError("container lab must not run as root")
    print(json.dumps({"cgroup_limits": read_limits(root)}), flush=True)
    try:
        sample = measure(model_dir, rows, density, mode, **(
            {} if cache_phase is None else {"cache_dir": cache_dir, "cache_phase": cache_phase}))
    finally:
        usage = read_usage(root)
        print(json.dumps({"cgroup_usage": usage}), flush=True)
    if not usage["within_limit_without_oom"]:
        raise RuntimeError("cgroup peak or OOM check failed")
    print(json.dumps({"capacity": sample}), flush=True)


def read_reports(*paths):
    reports = []
    for path in paths:
        entries = [json.loads(line) for line in path.read_text().splitlines()]
        if [set(entry) for entry in entries] != [{"cgroup_limits"}, {"cgroup_usage"}, {"capacity"}]:
            raise ValueError("incomplete or malformed cgroup report")
        limit, usage, sample = (next(iter(entry.values())) for entry in entries)
        if (limit["cpu_quota_us"] != 2 * limit["cpu_period_us"] or limit["cpu_period_us"] <= 0
                or limit["memory_limit_bytes"] != 2 * 1024**3 or limit["swap_limit_bytes"] != 0
                or not usage["within_limit_without_oom"] or not 0 < usage["peak_bytes"] <= 2 * 1024**3
                or any(usage[key] != 0 for key in ("oom", "oom_kill", "oom_group_kill"))
                or sample["fixture"] != "synthetic_qa_only" or sample["rows"] not in _ROWS
                or sample["density"] not in _DENSITIES or sample["warm_samples"] != 21
                or not re.fullmatch(r"[0-9a-f]{64}", sample["catalog_sha256"])
                or sample["warm_p95_ms"] < sample["warm_p50_ms"]
                or any(not isfinite(sample[key]) or sample[key] <= 0 for key in
                       ("process_ready_seconds", "first_http_ms", "warm_p50_ms", "warm_p95_ms"))
                or not valid_results(sample["ordered_typed_results"], sample["rows"])):
            raise ValueError("report does not meet synthetic acceptance criteria")
        reports.append(sample)
    return reports


def compare(baseline, prepared):
    """Compare two successful captures; metrics are not used as a parity proxy."""
    a, b = read_reports(baseline, prepared)
    if (a["mode"], b["mode"]) != _MODES or any(a[key] != b[key] for key in
            ("rows", "density", "catalog_sha256", "ordered_typed_results")):
        raise ValueError("baseline/prepared workload or final typed Top-5 order differs")
    print(json.dumps({"paired_typed_top5": len(a["ordered_typed_results"]), "rows": a["rows"],
                      "density": a["density"], "parity": True, "synthetic_only": True}), flush=True)


def compare_restart(cold, restart):
    a, b = read_reports(cold, restart)
    common = ("catalog_sha256", "passage_snapshot_id", "passage_snapshot_sha256", "ordered_typed_results")
    for sample, phase, hit in ((a, "cold", False), (b, "restart", True)):
        if ((sample["rows"], sample["density"], sample["mode"], sample.get("cache_phase"))
                != (1000, "high", "prepared", phase)
                or sample.get("proof_of_cache_hit") is not hit
                or any(not re.fullmatch(r"[0-9a-f]{64}", sample.get(key, ""))
                       for key in common[1:3])):
            raise ValueError("unexpected workload, cache identity or missing restart proof")
    if any(a[key] != b[key] for key in common):
        raise ValueError("restart did not preserve exact snapshot and typed Top-5")
    print(json.dumps({"paired_typed_top5": len(a["ordered_typed_results"]),
                      "rows": 1000, "density": "high", "mode": "prepared",
                      "cache_hit_proven": True, "snapshot_unchanged": True, "synthetic_only": True}), flush=True)


def valid_results(results, rows):
    expected = {(media, f"tmdb:{media}:{2147482000 + index // 2}")
                for index in range(rows) for media in (("movie", "tv")[index % 2],)}
    if not isinstance(results, list) or len(results) != 7:
        return False
    for probe in results:
        if not isinstance(probe, list) or len(probe) != 5:
            return False
        keys = [tuple(card) for card in probe]
        if len(set(keys)) != 5 or not set(keys) <= expected:
            return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("run")
    probe.add_argument("--model-dir", type=Path, required=True)
    probe.add_argument("--rows", type=int, choices=_ROWS, required=True)
    probe.add_argument("--density", choices=_DENSITIES, required=True)
    probe.add_argument("--mode", choices=_MODES, required=True)
    probe.add_argument("--cache-dir", type=Path)
    probe.add_argument("--cache-phase", choices=_CACHE_PHASES)
    pairing = sub.add_parser("compare")
    pairing.add_argument("baseline", type=Path)
    pairing.add_argument("prepared", type=Path)
    restart = sub.add_parser("compare-restart")
    restart.add_argument("cold", type=Path)
    restart.add_argument("restart", type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        if (args.cache_phase is None) != (args.cache_dir is None) or (
                args.cache_phase is not None and (args.rows, args.density, args.mode) != (1000, "high", "prepared")):
            parser.error("cache lab needs both cache arguments and 1000/high/prepared")
        run(args.model_dir, args.rows, args.density, args.mode,
            cache_dir=args.cache_dir, cache_phase=args.cache_phase)
    elif args.command == "compare":
        compare(args.baseline, args.prepared)
    else:
        compare_restart(args.cold, args.restart)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
