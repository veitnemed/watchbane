"""Run diagnostic scenarios and write reports to logs/reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from diagnostics.runtime_reports import (  # noqa: E402
    DEFAULT_REPORTS_DIR,
    print_report_result,
    run_add_title_report,
    run_command_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a scenario and save runtime report.")
    parser.add_argument(
        "--reports-dir",
        default=str(DEFAULT_REPORTS_DIR),
        help="Directory for JSON/TXT reports. Default: logs/reports",
    )
    subparsers = parser.add_subparsers(dest="scenario", required=True)

    add_title = subparsers.add_parser("add-title", help="Trace add-title resolve flow.")
    add_title.add_argument("--title", required=True, help="Title to resolve.")
    add_title.add_argument("--country", default="Россия", help="Country filter. Default: Россия")

    command = subparsers.add_parser("command", help="Run any command and capture stdout/stderr.")
    command.add_argument("--name", required=True, help="Short report scenario name.")
    command.add_argument("--timeout", type=int, default=None, help="Timeout in seconds.")
    command.add_argument("command", nargs=argparse.REMAINDER, help="Command after --, for example: -- python -m pytest")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.scenario == "add-title":
        report = run_add_title_report(
            args.title,
            args.country,
            reports_dir=args.reports_dir,
        )
        print_report_result(report)
        return

    if args.scenario == "command":
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise SystemExit("command scenario requires a command after --")
        report = run_command_report(
            args.name,
            command,
            reports_dir=args.reports_dir,
            timeout_seconds=args.timeout,
        )
        print_report_result(report)
        return

    raise SystemExit(f"Unknown scenario: {args.scenario}")


if __name__ == "__main__":
    main()
