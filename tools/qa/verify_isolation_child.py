"""Child process: prove config.constant.APP_DATA_DIR is under WATCHBANE_DATA_DIR.

Must be launched only via ``tools.qa.run_recommendation_audit`` (or equivalent)
after ``WATCHBANE_DATA_DIR`` is already set in the process environment.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config.app_paths import DATA_DIR_ENV


def main() -> int:
    runtime = str(os.environ.get(DATA_DIR_ENV) or "").strip()
    if not runtime:
        print("CHILD_FAIL: WATCHBANE_DATA_DIR is not set", file=sys.stderr)
        return 2

    runtime_root = Path(runtime).expanduser().resolve()
    # Import constant only after env is present in this process.
    from config import constant

    app_data_dir = Path(str(constant.APP_DATA_DIR)).expanduser().resolve()
    try:
        app_data_dir.relative_to(runtime_root)
        isolated = True
    except ValueError:
        isolated = False

    evidence_override = str(os.environ.get("WATCHBANE_QA_EVIDENCE_DIR") or "").strip()
    evidence_dir = (
        Path(evidence_override).expanduser().resolve()
        if evidence_override
        else (runtime_root / "qa_evidence")
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    proof = {
        "WATCHBANE_DATA_DIR": str(runtime_root),
        "APP_DATA_DIR": str(app_data_dir),
        "isolated": isolated,
        "marker_present": (runtime_root / ".watchbane_qa_isolated").is_file(),
    }
    proof_path = evidence_dir / "child_isolation_proof.json"
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not isolated:
        print(
            f"CHILD_FAIL: APP_DATA_DIR={app_data_dir} is outside runtime={runtime_root}",
            file=sys.stderr,
        )
        return 3

    print(f"CHILD_OK APP_DATA_DIR={app_data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
