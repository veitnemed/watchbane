"""One-time migration to strip legacy KP/IMDb fields from candidate pool payloads."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from candidates.models.schema import EXTERNAL_RATING_FIELDS, strip_external_rating_fields

REPORT_PATH = ROOT_DIR / "data" / "diagnostics" / "candidate_kp_imdb_strip_migration_report.json"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def migrate_sqlite_candidates(db_path: Path, *, dry_run: bool = False) -> dict[str, int]:
    try:
        import sqlite3
    except ImportError:
        return {"sqlite_records_migrated": 0}

    if not db_path.exists():
        return {"sqlite_records_migrated": 0}

    from storage.sqlite.json_codec import dumps_json, loads_json
    from storage.sqlite.session import utc_now

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT pool_key, payload_json FROM candidate_records"
        ).fetchall()
        migrated = 0
        timestamp = utc_now()
        for pool_key, payload_text in rows:
            payload = loads_json(payload_text, {})
            if not isinstance(payload, dict):
                continue
            stripped = strip_external_rating_fields(payload)
            if stripped == payload:
                continue
            migrated += 1
            if dry_run:
                continue
            connection.execute(
                """
                UPDATE candidate_records
                SET payload_json = ?, updated_at = ?
                WHERE pool_key = ?
                """,
                (dumps_json(stripped), timestamp, pool_key),
            )
        if dry_run is False:
            connection.commit()
        return {"sqlite_records_migrated": migrated, "fields": sorted(EXTERNAL_RATING_FIELDS)}
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Strip legacy KP/IMDb fields from candidate payloads.")
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write files.")
    parser.add_argument(
        "--sqlite",
        default=str(ROOT_DIR / "data" / "watchbane.sqlite3"),
        help="SQLite DB path.",
    )
    args = parser.parse_args()

    stats = migrate_sqlite_candidates(Path(args.sqlite), dry_run=args.dry_run)
    report = {
        "timestamp": _timestamp(),
        "dry_run": args.dry_run,
        "paths": {"sqlite": args.sqlite},
        "stats": stats,
    }

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
