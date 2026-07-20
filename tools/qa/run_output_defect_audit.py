"""C3-12 isolated output-defect audit for all onboarding presets and synthetic decks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.qa.output_defect_audit import build_output_defect_audit
from tools.qa.run_synthetic_taste_profile_evaluation import main as run_synthetic_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    code = run_synthetic_evaluation(
        ["--runtime-root", str(args.runtime_root), "--output-dir", str(args.output_dir)]
    )
    if code != 0:
        return code
    reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(args.output_dir.resolve().glob("P*.json"))
    ]
    audit = build_output_defect_audit(reports)
    audit_path = args.output_dir.resolve() / "output_defect_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OUTPUT_DEFECT_AUDIT_{'OK' if audit['passed'] else 'FAIL'} report={audit_path}")
    return 0 if audit["passed"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
