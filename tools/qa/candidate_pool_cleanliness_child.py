"""Isolated child that writes one C3-13 pool-cleanliness JSON report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not os.environ.get("WATCHBANE_DATA_DIR"):
        return 2
    from config.constant import APP_DATA_DIR
    from tools.qa.candidate_pool_cleanliness_audit import (
        audit_candidate_pool,
        load_audit_state_read_only,
        load_pool_read_only,
    )

    now = datetime.now(timezone.utc)
    runtime_root = Path(os.environ["WATCHBANE_DATA_DIR"]).resolve()
    db_path = Path(APP_DATA_DIR) / "watchbane.sqlite3"
    try:
        Path(APP_DATA_DIR).resolve().relative_to(runtime_root)
        isolated = True
    except ValueError:
        isolated = False
    evidence_dir = Path(os.environ.get("WATCHBANE_QA_EVIDENCE_DIR") or (runtime_root / "qa_evidence")).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "child_isolation_proof.json").write_text(
        json.dumps({
            "WATCHBANE_DATA_DIR": str(runtime_root), "APP_DATA_DIR": str(Path(APP_DATA_DIR).resolve()),
            "isolated": isolated, "marker_present": (runtime_root / ".watchbane_qa_isolated").is_file(),
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not isolated:
        return 3
    state = load_audit_state_read_only(db_path, now=now)
    pool = load_pool_read_only(db_path)
    report = audit_candidate_pool(pool, state=state, now=now)
    report["head_commit"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False).stdout.strip() or "unknown"
    report["production_context"]["runtime_db"] = str(db_path.resolve())
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"C3_13_AUDIT_OK output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
