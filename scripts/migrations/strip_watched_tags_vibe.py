"""One-time migration to strip legacy tags_vibe from watched records."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import constant

REPORT_PATH = ROOT_DIR / "data" / "diagnostics" / "watched_tags_vibe_strip_migration_report.json"
LEGACY_SECTION = constant.TAGS_VIBE_SECTION


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def watched_path() -> Path:
    return _json_path(constant.FILE_NAME)


def meta_path() -> Path:
    return _json_path(constant.META_JSON)


def backup_path_for(path: Path, timestamp: str) -> Path:
    return path.with_name(f"{path.stem}.before_tags_vibe_strip.{timestamp}{path.suffix}")


def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def strip_tags_vibe(movie: dict[str, Any]) -> bool:
    if not isinstance(movie, dict):
        return False
    return movie.pop(LEGACY_SECTION, None) is not None


def migrate_watched_tags_vibe(
    dataset: dict[str, Any],
    meta: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    migrated_dataset = dict(dataset if isinstance(dataset, dict) else {})
    migrated_meta = dict(meta if isinstance(meta, dict) else {})
    stats = {
        "total_watched": len(migrated_dataset),
        "dataset_records_migrated": 0,
        "meta_records_migrated": 0,
    }

    for title, movie in list(migrated_dataset.items()):
        if strip_tags_vibe(movie):
            migrated_dataset[title] = movie
            stats["dataset_records_migrated"] += 1

    for title, movie in list(migrated_meta.items()):
        if isinstance(movie, dict) and strip_tags_vibe(movie):
            migrated_meta[title] = movie
            stats["meta_records_migrated"] += 1

    return migrated_dataset, migrated_meta, stats


def migrate_sqlite_watched(db_path: Path) -> dict[str, int]:
    try:
        import sqlite3
    except ImportError:
        return {"sqlite_records_migrated": 0}

    if not db_path.exists():
        return {"sqlite_records_migrated": 0}

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.execute(
            "SELECT id, payload FROM watched_records WHERE payload LIKE ?",
            (f'%"{LEGACY_SECTION}"%',),
        )
        rows = cursor.fetchall()
        migrated = 0
        for record_id, payload_text in rows:
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                continue
            if strip_tags_vibe(payload):
                connection.execute(
                    "UPDATE watched_records SET payload = ? WHERE id = ?",
                    (json.dumps(payload, ensure_ascii=False), record_id),
                )
                migrated += 1
        connection.commit()
        return {"sqlite_records_migrated": migrated}
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Strip legacy tags_vibe from watched records.")
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write files.")
    parser.add_argument(
        "--sqlite",
        default=str(ROOT_DIR / "data" / "watchbane.sqlite3"),
        help="Optional SQLite watched DB path.",
    )
    args = parser.parse_args()

    watched = watched_path()
    meta = meta_path()
    dataset = read_json(watched)
    meta_data = read_json(meta)
    migrated_dataset, migrated_meta, stats = migrate_watched_tags_vibe(dataset, meta_data)
    stats.update(migrate_sqlite_watched(Path(args.sqlite)))

    report = {
        "timestamp": _timestamp(),
        "dry_run": args.dry_run,
        "paths": {
            "watched_json": str(watched),
            "meta_json": str(meta),
            "sqlite": args.sqlite,
        },
        "stats": stats,
    }

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    timestamp = report["timestamp"]
    if watched.exists():
        shutil.copy2(watched, backup_path_for(watched, timestamp))
        write_json(watched, migrated_dataset)
    if meta.exists():
        shutil.copy2(meta, backup_path_for(meta, timestamp))
        write_json(meta, migrated_meta)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(REPORT_PATH, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
