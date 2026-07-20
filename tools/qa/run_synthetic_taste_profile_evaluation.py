"""Safe parent launcher for C3-10 synthetic taste-profile evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.qa.run_recommendation_audit import main as run_isolated_audit


CHILD = Path(__file__).resolve().with_name("synthetic_taste_profiles_child.py")
DEFAULT_PROFILES_DIR = Path(__file__).resolve().parent / "fixtures" / "synthetic_taste_profiles"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_isolated_audit(
        [
            "--runtime-root",
            str(args.runtime_root),
            "--child",
            str(CHILD),
            "--evidence-dir",
            str(args.output_dir),
            "--",
            "--profiles-dir",
            str(args.profiles_dir),
            "--output-dir",
            str(args.output_dir),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
