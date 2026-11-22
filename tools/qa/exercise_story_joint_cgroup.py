"""Synthetic strict prebuilt handover; native acceptance needs one fresh shared ARM64 cgroup."""
import argparse
from contextlib import ExitStack
from hashlib import sha256
from http.client import HTTPException
import json
import os
from pathlib import Path
import platform
import re
import sys

from tools.qa.exercise_story_handover import ExerciseError, ReadinessTimeout, launch, request, wait_health
from tools.qa.prebuild_story_passages import prebuild, private_directory
from tools.qa.smoke_story_arm_cgroup import ROOT, read_limits, read_usage


_NUMBER = 2147482009  # Disposable fixture only; no provider lookup.
_PHASES = ("old", "new")
_WAIT = 30
_BATCH = 4


def fixture(generation):
    return (
        {"media_type": "movie", "tmdb_id": _NUMBER, "title": "Синтетический фильм",
         "overview": ("Альпинист закрывает горную станцию до прихода бури." if generation == "old"
                      else "Альпинист открывает горную станцию после ухода бури."),
         "language": "ru-RU", "year": 2000},
        {"media_type": "tv", "tmdb_id": _NUMBER, "title": "Синтетический сериал",
         "overview": "Доктор вспоминает разговор с пациентом в пустой больнице.",
         "language": "ru-RU", "year": 2010},
    )


def fixture_bytes(generation):
    return "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                   for row in fixture(generation)).encode("utf-8")


def prepare(bundle, model):
    """Prebuild outside the measured cgroup to isolate the two-process peak."""
    bundle = private_directory(bundle)
    if any(bundle.iterdir()):
        raise ValueError("Preparation requires an empty private bundle directory.")
    manifest = {}
    for generation in _PHASES:
        folder = bundle / generation
        folder.mkdir(mode=0o700)
        catalog = folder / "synthetic.jsonl"
        data = fixture_bytes(generation)
        catalog.write_bytes(data)
        cache = folder / "cache"
        cache.mkdir(mode=0o700)
        report = prebuild(catalog, sha256(data).hexdigest(), model, cache, batch_size=_BATCH)
        manifest[generation] = [report["catalog_sha256"], report["snapshot_sha256"]]
    with (bundle / "pins.json").open("x", encoding="utf-8") as file:
        json.dump(manifest, file)
    return {"synthetic_only": True, "generations_prebuilt": len(manifest), "rows_per_generation": 2}


def validated_bundle(bundle):
    bundle = private_directory(bundle)
    with (bundle / "pins.json").open("rb") as file:
        raw = file.read(1025)
    if len(raw) > 1024:
        raise ValueError("Invalid synthetic QA bundle metadata.")
    pins = json.loads(raw)
    if not isinstance(pins, dict) or set(pins) != set(_PHASES):
        raise ValueError("Invalid synthetic QA bundle metadata.")
    for generation, pair in pins.items():
        if (not isinstance(pair, list) or len(pair) != 2
                or any(not isinstance(d, str) or re.fullmatch(r"[0-9a-f]{64}", d) is None for d in pair)
                or pair[0] != sha256(fixture_bytes(generation)).hexdigest()):
            raise ValueError("Invalid synthetic QA bundle pins.")
    return bundle, pins


def verify(server, expected_generation):
    if server[1].poll() is not None:
        raise ExerciseError("Selected process has exited.")
    cards = []
    queries = ("фильм про альпиниста и горную станцию", "сериал про доктора в больнице")
    for query, fixture_row in zip(queries, fixture(expected_generation), strict=True):
        body = json.dumps({"query": query, "limit": 1}, ensure_ascii=False).encode("utf-8")
        expected = {key: value for key, value in fixture_row.items() if key != "tmdb_id"}
        expected.update(id=f"tmdb:{fixture_row['media_type']}:{_NUMBER}", evidence=fixture_row["overview"])
        result = request(server[0], "/v1/search", body)
        if result != {"source": "tmdb", "results": [expected]}:
            raise ExerciseError("Typed generation or unaffected TV payload differs.")
        cards.append(result)
    return cards


def exercise(bundle, model, *, capped, root=ROOT, proc=Path("/proc")):
    bundle, pins = validated_bundle(bundle)
    report = {"synthetic_only": True, "shared_cgroup_enforced": capped,
              "startup_budget_seconds": _WAIT, "old_while_new_unready": 0}
    if capped:
        if ((platform.system(), platform.machine(), sys.version_info[:3])
                != ("Linux", "aarch64", (3, 12, 16)) or os.geteuid() == 0):
            raise ValueError("Expected native Linux ARM64, pinned Python, non-root.")
        report["limits"] = read_limits(root)
        first_usage = read_usage(root)
        if (not first_usage["within_limit_without_oom"]
                or any(first_usage[key] for key in ("oom", "oom_kill", "oom_group_kill", "memory_max_events"))):
            raise ValueError("Expected a fresh cgroup without prior limit or OOM events.")
        parent_group = (proc / "self/cgroup").read_text().strip()
        if parent_group != "0::/":
            raise ValueError("Expected one private root cgroup namespace.")

    phase = "initialization"
    children = {}
    with ExitStack() as processes:
        try:
            def start(name):
                folder = bundle / name
                server = processes.enter_context(launch(folder / "synthetic.jsonl", model, _BATCH,
                                                        cache_dir=folder / "cache", prepared_index=True,
                                                        strict_pins=pins[name]))
                children[name] = server[1]
                return server

            phase = "start_old"
            old = start("old")
            report["old_ready_s"] = round(wait_health(old, _WAIT), 3)
            phase = "verify_old"
            baseline = verify(old, "old")
            if capped:
                report["old_only_memory_current_bytes"] = int((root / "memory.current").read_text())
            active = old

            phase = "stage_new"
            new = start("new")

            def old_stays_active():
                if report["old_while_new_unready"] < 3:
                    if verify(active, "old") != baseline:
                        raise ExerciseError("Old route changed during staging.")
                    try:
                        candidate_ready = request(new[0], "/healthz") == {"ready": True}
                    except (OSError, HTTPException, ValueError, ExerciseError):
                        candidate_ready = False
                    if new[1].poll() is not None:
                        raise ExerciseError("Candidate exited during staging.")
                    if not candidate_ready:
                        report["old_while_new_unready"] += 1

            report["new_ready_s"] = round(wait_health(new, _WAIT, on_not_ready=old_stays_active), 3)
            if not report["old_while_new_unready"]:
                raise ExerciseError("No old response was witnessed during candidate readiness.")
            phase = "verified_overlap"
            if capped:
                for child in children.values():
                    if (proc / str(child.pid) / "cgroup").read_text().strip() != parent_group:
                        raise ExerciseError("Child escaped the common cgroup.")
                report["both_children_same_cgroup"] = True
            candidate = verify(new, "new")
            if verify(active, "old") != baseline or candidate[1] != baseline[1]:
                raise ExerciseError("Overlap changed old or unaffected results.")
            if capped:
                report["overlap_usage"] = read_usage(root)
                report["overlap_memory_current_bytes"] = int((root / "memory.current").read_text())
            phase = "switch"
            active = new
            if verify(active, "new") != candidate:
                raise ExerciseError("Selected new results differ.")
            phase = "rollback"
            active = old
            if verify(active, "old") != baseline:
                raise ExerciseError("Rollback did not restore the old result.")
            if any(child.poll() is not None for child in children.values()):
                raise ExerciseError("A process did not survive the overlap and rollback.")
            report["switched_and_rolled_back"] = True
        except (ExerciseError, ValueError, OSError, HTTPException) as error:
            report["failure"] = "readiness_timeout" if isinstance(error, ReadinessTimeout) else "probe_or_process_failure"
            report["failure_phase"] = phase
            report["child_exit_status"] = {name: child.poll() for name, child in children.items()}
        finally:
            if capped:
                report["final_usage"] = usage = read_usage(root)
                if any(usage[key] for key in ("oom", "oom_kill", "oom_group_kill")):
                    report["resource_failure"] = "oom_event"
                elif not usage["within_limit_without_oom"] or usage["memory_max_events"] != 0:
                    report["resource_failure"] = "memory_limit_event"
    report["passed"] = bool(report.get("switched_and_rolled_back")
                            and not report.get("failure") and not report.get("resource_failure"))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
        epilog=("Prepare using the same native image in a separate invocation; mount the private "
                "bundle read-only. Apply an outer 90-second "
                "wall timeout and inspect the container exit/OOM status even if the lab cannot report."))
    sub = parser.add_subparsers(dest="phase", required=True)
    for name in ("prepare", "exercise"):
        phase = sub.add_parser(name)
        phase.add_argument("--bundle-dir", required=True, type=Path)
        phase.add_argument("--model-dir", required=True, type=Path)
        if name == "exercise":
            cap = phase.add_mutually_exclusive_group(required=True)
            cap.add_argument("--require-native-arm-cgroup", action="store_true")
            cap.add_argument("--unbounded-local-development", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = (prepare(args.bundle_dir, args.model_dir) if args.phase == "prepare"
                  else exercise(args.bundle_dir, args.model_dir, capped=args.require_native_arm_cgroup))
    except (ExerciseError, OSError, ValueError, RuntimeError):
        print("Synthetic handover refused before completing its local verification.", file=sys.stderr)
        return 1
    print(json.dumps(report), flush=True)
    return 0 if report.get("passed", args.phase == "prepare") else 1


if __name__ == "__main__":
    raise SystemExit(main())
