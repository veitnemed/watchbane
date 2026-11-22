"""Native ARM64 gate for the existing synthetic local TCP generation rehearsal."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import platform
import sys

from tools.qa.exercise_story_generation_tcp import rehearse
from tools.qa.smoke_story_arm_cgroup import ROOT, read_limits, read_usage


_APP_WALL_SECONDS = 75  # Host also enforces a hard stop for stuck runtime threads.
_CONTROLLED = ("synthetic_only", "one_tcp_listener", "strict_artwork_index_outcome", "corruption_refused",
               "controlled_staging_old_ready", "stale_capture_old", "inflight_busy", "rollback")


async def bounded_rehearsal(bundle, model, rows):
    return await asyncio.wait_for(rehearse(bundle, model, scale=rows), timeout=_APP_WALL_SECONDS)


def run(bundle, model, *, rows, root=ROOT, proc=Path("/proc")):
    if rows != 1000:
        raise ValueError("Expected the 1000-row synthetic TCP lab.")
    if ((platform.system(), platform.machine(), sys.version_info[:3]) != ("Linux", "aarch64", (3, 12, 16))
            or os.geteuid() == 0 or (proc / "self/cgroup").read_text().strip() != "0::/"):
        raise ValueError("Expected one private, pinned non-root native ARM64 cgroup.")
    report = {"synthetic_only": True, "rows_per_generation": rows, "transport": "private_ipv4_loopback_tcp",
              "app_wall_budget_seconds": _APP_WALL_SECONDS, "cgroup_limits": read_limits(root),
              "passive_samples_not_sla": True}
    before = read_usage(root)
    if not before["within_limit_without_oom"] or before["memory_max_events"]:
        raise ValueError("Expected a fresh cgroup without prior memory-limit events.")
    report["memory_current_before_bytes"] = int((root / "memory.current").read_text())
    try:
        result = asyncio.run(bounded_rehearsal(bundle, model, rows))
        if (result["rows"] != [rows, rows] or result["verified_model_sessions"] != 1
                or result["forbidden_startup_encodes"] != 0
                or type(result.get("actual_query_calls")) is not int or result["actual_query_calls"] <= 0
                or not all(result.get(key) is True for key in _CONTROLLED)):
            raise ValueError("Controlled TCP rehearsal did not prove the expected invariants.")
        report["passive_unpaused_observation"] = result["unpaused"]
        report["controlled_switch_and_metadata"] = {
            key: result[key] for key in (*_CONTROLLED, "rows", "verified_model_sessions",
                                         "forbidden_startup_encodes", "actual_query_calls")}
    except TimeoutError:
        report["failure"] = "controlled_tcp_deadline"
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        report["failure"] = "controlled_tcp_or_rehearsal_failure"
    finally:
        report["memory_current_after_bytes"] = int((root / "memory.current").read_text())
        report["cgroup_usage"] = usage = read_usage(root)
        if any(usage[key] for key in ("oom", "oom_kill", "oom_group_kill")):
            report["resource_failure"] = "oom_event"
        elif not usage["within_limit_without_oom"] or usage["memory_max_events"]:
            report["resource_failure"] = "memory_limit_event"
    report["passed"] = "controlled_switch_and_metadata" in report and not (
        report.get("failure") or report.get("resource_failure"))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, epilog="Use the exact prepared bundle read-only. No ports are published; no SLA claims.")
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--rows", required=True, type=int, choices=(1000,))
    args = parser.parse_args(argv)
    try:
        report = run(args.bundle_dir, args.model_dir, rows=args.rows)
    except (OSError, RuntimeError, ValueError):
        print("Native TCP rehearsal refused before completing the cgroup gate.", file=sys.stderr)
        return 1
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
