"""Isolated child for C3-10 synthetic taste-profile evaluation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    return (completed.stdout or "").strip() if completed.returncode == 0 else "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime_text = str(os.environ.get("WATCHBANE_DATA_DIR") or "").strip()
    if not runtime_text:
        print("SYNTHETIC_PROFILE_FAIL: WATCHBANE_DATA_DIR is not set", file=sys.stderr)
        return 2
    runtime_root = Path(runtime_text).expanduser().resolve()
    if not (runtime_root / ".watchbane_qa_isolated").is_file():
        print("SYNTHETIC_PROFILE_FAIL: isolated runtime marker is missing", file=sys.stderr)
        return 2

    from common.release import APP_VERSION
    from config.constant import APP_DATA_DIR
    from tools.qa.synthetic_taste_profiles import TasteProfileError, evaluate_profile, load_profile

    app_data_dir = Path(APP_DATA_DIR).resolve()
    try:
        app_data_dir.relative_to(runtime_root)
        isolated = True
    except ValueError:
        isolated = False

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    proof_path = output_dir / "child_isolation_proof.json"
    proof_path.write_text(
        json.dumps(
            {
                "WATCHBANE_DATA_DIR": str(runtime_root),
                "APP_DATA_DIR": str(app_data_dir),
                "isolated": isolated,
                "marker_present": (runtime_root / ".watchbane_qa_isolated").is_file(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if not isolated:
        print("SYNTHETIC_PROFILE_FAIL: APP_DATA_DIR is outside the isolated runtime", file=sys.stderr)
        return 3

    profiles_dir = args.profiles_dir.resolve()
    profile_paths = sorted(profiles_dir.glob("*.json"))
    if not profile_paths:
        print(f"SYNTHETIC_PROFILE_FAIL: no profiles in {profiles_dir}", file=sys.stderr)
        return 2

    reports: list[dict] = []
    try:
        for path in profile_paths:
            profile = load_profile(path)
            report = evaluate_profile(
                profile,
                runtime_root=runtime_root,
                app_data_dir=app_data_dir,
                commit=_git_commit() or "unknown",
                app_version=APP_VERSION,
            )
            report_path = output_dir / f"{profile.profile_id}.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            reports.append({"profile_id": profile.profile_id, "report": str(report_path)})
    except TasteProfileError as error:
        print(f"SYNTHETIC_PROFILE_FAIL: {error}", file=sys.stderr)
        return 2

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps({"reports": reports}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SYNTHETIC_PROFILE_OK reports={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
