"""Lab-only actual cgroup budget check for one synthetic loopback E5 smoke."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys

from tools.qa.smoke_story_arm_http import smoke


MEMORY_BYTES = 2 * 1024**3
ROOT = Path("/sys/fs/cgroup")


def read_limits(root):
    """Require effective cgroup v2 settings, not just requested Docker flags."""
    if not (root / "cgroup.controllers").is_file():
        raise RuntimeError("cgroup v2 is required")
    quota, period = (root / "cpu.max").read_text().split()
    if not (quota.isdecimal() and period.isdecimal() and int(period) > 0
            and int(quota) == 2 * int(period)):
        raise RuntimeError("expected a two-CPU cgroup quota")
    if (root / "memory.max").read_text().strip() != str(MEMORY_BYTES):
        raise RuntimeError("expected a 2 GiB cgroup memory limit")
    if (root / "memory.swap.max").read_text().strip() != "0":
        raise RuntimeError("expected no cgroup swap")
    return {"cpu_quota_us": int(quota), "cpu_period_us": int(period),
            "memory_limit_bytes": MEMORY_BYTES, "swap_limit_bytes": 0}


def read_usage(root):
    events = {key: int(value) for key, value in
              (line.split() for line in (root / "memory.events").read_text().splitlines())}
    peak = int((root / "memory.peak").read_text())
    limits_ok = 0 < peak <= MEMORY_BYTES and events["oom"] == events["oom_kill"] == 0
    group_kills = events.get("oom_group_kill", 0)
    return {"peak_bytes": peak, "oom": events["oom"], "oom_kill": events["oom_kill"],
            "oom_group_kill": group_kills, "memory_max_events": events.get("max", 0), "within_limit_without_oom": limits_ok and group_kills == 0}


def run(model_dir, *, root=ROOT):
    # Host verification may already warm the kernel page cache. This checks
    # a fresh container/process, not evicted page-cache startup.
    if (platform.system(), platform.machine(), sys.version_info[:3]) != ("Linux", "aarch64", (3, 12, 16)):
        raise RuntimeError("requires native Linux ARM64 and the pinned Python 3.12.16 image")
    if os.geteuid() == 0:
        raise RuntimeError("container smoke must not run as root")
    print(json.dumps({"cgroup_limits": read_limits(root)}), flush=True)
    result = None
    try:
        result = smoke(model_dir, require_native_arm=True)
        print(json.dumps({"synthetic_loopback_probe": result}), flush=True)
    finally:
        usage = read_usage(root)
        print(json.dumps({"cgroup_usage": usage}), flush=True)
    if not usage["within_limit_without_oom"]:
        raise RuntimeError("cgroup peak or oom check failed")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    run(args.model_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
