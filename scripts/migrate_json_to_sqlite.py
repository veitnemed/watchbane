"""Import legacy Watchbane JSON runtime data into SQLite."""

from __future__ import annotations

import argparse
import json

from storage.sqlite.import_legacy import import_legacy_json_to_sqlite


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Watchbane JSON data into SQLite.")
    parser.add_argument("--base-dir", default="data", help="Legacy data directory.")
    parser.add_argument("--db-path", default=None, help="Target SQLite database path.")
    parser.add_argument("--dry-run", action="store_true", help="Read JSON and print counts without writing SQLite.")
    parser.add_argument("--no-backup", action="store_true", help="Skip legacy JSON backup before import.")
    args = parser.parse_args()

    report = import_legacy_json_to_sqlite(
        base_dir=args.base_dir,
        db_path=args.db_path,
        dry_run=args.dry_run,
        create_backup=not args.no_backup,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

