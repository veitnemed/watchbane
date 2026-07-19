"""Safe parent entry for recommendation QA audits (C3-06).

Sets ``WATCHBANE_DATA_DIR`` and validates isolation **before** spawning a child
that may import ``config.constant``. This parent must not import
``config.constant``, ``candidates``, ``desktop``, ``storage``, or ``apis``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Allowed project imports: app_paths + this package's isolation helpers only.
from config.app_paths import DATA_DIR_ENV
from tools.qa.isolation import (
    IsolationError,
    apply_isolated_data_dir,
    assert_runtime_is_isolated,
    real_watchbane_profile_root,
    utc_now_iso,
    write_isolation_marker,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHILD = Path(__file__).resolve().parent / "verify_isolation_child.py"


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return (completed.stdout or "").strip() or "unknown"
    except OSError:
        pass
    return "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Safe isolated launcher for recommendation QA audits. "
            "Requires an explicit --runtime-root outside the real Watchbane profile."
        )
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        required=True,
        help=f"Isolated runtime directory (sets {DATA_DIR_ENV}). Required; no silent default.",
    )
    parser.add_argument(
        "--child",
        type=Path,
        default=DEFAULT_CHILD,
        help="Child script run after isolation is confirmed (default: verify_isolation_child.py).",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=None,
        help="Where to write isolation_meta.json (default: <runtime-root>/qa_evidence).",
    )
    parser.add_argument(
        "child_args",
        nargs=argparse.REMAINDER,
        help="Optional args forwarded to the child after --.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    child_args = list(args.child_args or [])
    if child_args and child_args[0] == "--":
        child_args = child_args[1:]

    real_root = real_watchbane_profile_root()
    try:
        runtime_root = assert_runtime_is_isolated(args.runtime_root, real_root=real_root)
    except IsolationError as error:
        print(f"ISOLATION_FAIL: {error}", file=sys.stderr)
        return 2

    # Set env only after validation — still before any constant import in child.
    apply_isolated_data_dir(runtime_root)
    evidence_dir = (args.evidence_dir or (runtime_root / "qa_evidence")).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "task_id": "C3-06",
        "purpose": "Prevent QA-DEFECT-03 (early import freezing APP_DATA_DIR to real profile)",
        "started_utc": utc_now_iso(),
        "commit": _git_commit(),
        "runtime_root": str(runtime_root),
        "real_watchbane_profile_root": str(real_root),
        "WATCHBANE_DATA_DIR": os.environ.get(DATA_DIR_ENV),
        "isolation_check": "pending_child",
        "child": str(Path(args.child).resolve()),
        "note": "Does not clean possible prior contamination of the real profile.",
    }
    write_isolation_marker(runtime_root, meta=meta)

    child_path = Path(args.child).resolve()
    if child_path.is_file() is False:
        print(f"ISOLATION_FAIL: child script not found: {child_path}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env[DATA_DIR_ENV] = str(runtime_root)
    env["WATCHBANE_QA_EVIDENCE_DIR"] = str(evidence_dir)
    existing_pythonpath = str(env.get("PYTHONPATH") or "").strip()
    env["PYTHONPATH"] = (
        str(REPO_ROOT)
        if not existing_pythonpath
        else os.pathsep.join([str(REPO_ROOT), existing_pythonpath])
    )

    completed = subprocess.run(
        [sys.executable, str(child_path), *child_args],
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
    )
    meta["finished_utc"] = utc_now_iso()
    meta["child_exit_code"] = int(completed.returncode)

    proof_path = evidence_dir / "isolation_meta.json"
    child_proof = evidence_dir / "child_isolation_proof.json"
    if child_proof.is_file():
        try:
            meta["child_proof"] = json.loads(child_proof.read_text(encoding="utf-8"))
            child_app_data = str((meta["child_proof"] or {}).get("APP_DATA_DIR") or "")
            isolated_ok = bool((meta["child_proof"] or {}).get("isolated"))
            meta["isolation_check"] = "pass" if isolated_ok else "fail"
            meta["resolved_APP_DATA_DIR"] = child_app_data
        except (OSError, json.JSONDecodeError) as error:
            meta["isolation_check"] = "fail"
            meta["child_proof_error"] = str(error)
    else:
        meta["isolation_check"] = "fail" if completed.returncode == 0 else "fail"
        meta["child_proof_missing"] = str(child_proof)

    proof_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_isolation_marker(runtime_root, meta=meta)

    if completed.returncode != 0:
        print(
            f"ISOLATION_FAIL: child exited {completed.returncode}. See {proof_path}",
            file=sys.stderr,
        )
        return int(completed.returncode) or 1
    if meta.get("isolation_check") != "pass":
        print(f"ISOLATION_FAIL: child did not prove isolation. See {proof_path}", file=sys.stderr)
        return 3

    print(f"ISOLATION_OK runtime={runtime_root}")
    print(f"ISOLATION_OK evidence={proof_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
