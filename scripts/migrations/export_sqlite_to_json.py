"""Export Watchbane SQLite data to explicit legacy JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from storage.legacy_json.exporter import export_sqlite_to_legacy_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Watchbane SQLite data to legacy JSON files.")
    parser.add_argument("--output-dir", required=True, help="Directory for legacy JSON files.")
    parser.add_argument("--db-path", default=None, help="Source SQLite database path.")
    args = parser.parse_args()

    report = export_sqlite_to_legacy_json(
        output_dir=args.output_dir,
        db_path=args.db_path,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

