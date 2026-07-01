"""CLI entrypoint for background candidate poster download jobs."""

from __future__ import annotations
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from posters import download_job


def main() -> None:
    # Keep this tiny wrapper so users keep using the same external command.
    # `_run` is internal and used by the background process only.
    exit_code = download_job.run_cli()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
