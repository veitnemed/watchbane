"""Legacy JSON candidate_pool repair tool for the TMDb-only contract."""

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

from candidates.models.schema import (
    EXTERNAL_RATING_FIELDS,
    normalize_candidate_for_storage,
    resolve_canonical_year,
    strip_external_rating_fields,
)
from scripts.migrations.legacy_paths import candidate_pool_json

REPORT_PATH = ROOT_DIR / "data" / "diagnostics" / "candidate_pool_tmdb_only_migration_report.json"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def candidate_pool_path() -> Path:
    path = candidate_pool_json(ROOT_DIR / "data")
    return path


def backup_path_for(pool_path: Path, timestamp: str) -> Path:
    return pool_path.with_name(f"{pool_path.stem}.before_tmdb_only.{timestamp}{pool_path.suffix}")


def _has_tmdb_id(candidate: dict[str, Any]) -> bool:
    value = candidate.get("tmdb_id")
    return value is not None and str(value).strip() != ""


def migrate_candidate(candidate: dict[str, Any]) -> tuple[dict[str, Any], int]:
    stripped_count = sum(1 for field_name in EXTERNAL_RATING_FIELDS if field_name in candidate)
    migrated = strip_external_rating_fields(candidate)
    migrated["source"] = "tmdb"
    migrated["source_provider"] = "tmdb"
    migrated["source_version"] = 2

    canonical_year = resolve_canonical_year(migrated)
    migrated["year"] = canonical_year

    migrated = normalize_candidate_for_storage(migrated)
    if not _has_tmdb_id(migrated):
        migrated["needs_tmdb_match"] = True
    return migrated, stripped_count


def migrate_pool(pool: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    migrated_pool: dict[str, Any] = {}
    stats = {
        "total_candidates": len(pool) if isinstance(pool, dict) else 0,
        "migrated_candidates": 0,
        "stripped_kp_imdb_fields_count": 0,
        "candidates_with_tmdb_id": 0,
        "candidates_without_tmdb_id": 0,
        "complete_after_migration": 0,
        "incomplete_after_migration": 0,
    }
    if not isinstance(pool, dict):
        return {}, stats

    for original_key, raw_candidate in pool.items():
        if not isinstance(raw_candidate, dict):
            migrated_pool[original_key] = raw_candidate
            continue

        migrated, stripped_count = migrate_candidate(raw_candidate)
        migrated_pool[str(original_key)] = migrated

        stats["migrated_candidates"] += 1
        stats["stripped_kp_imdb_fields_count"] += stripped_count
        if _has_tmdb_id(migrated):
            stats["candidates_with_tmdb_id"] += 1
        else:
            stats["candidates_without_tmdb_id"] += 1
        if migrated.get("is_complete") is True:
            stats["complete_after_migration"] += 1
        else:
            stats["incomplete_after_migration"] += 1

    return migrated_pool, stats


def read_pool(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def build_report(
    *,
    mode: str,
    pool_path: Path,
    backup_path: Path | None,
    stats: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": mode,
        "pool_path": str(pool_path),
        "backup_path": str(backup_path) if backup_path is not None else None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        **stats,
    }


def run_migration(*, apply: bool, report_path: Path = REPORT_PATH) -> dict[str, Any]:
    pool_path = candidate_pool_path()
    original_pool = read_pool(pool_path)
    migrated_pool, stats = migrate_pool(original_pool)

    backup_path = None
    if apply:
        timestamp = _timestamp()
        backup_path = backup_path_for(pool_path, timestamp)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if pool_path.exists():
            shutil.copy2(pool_path, backup_path)
        else:
            write_json(backup_path, original_pool)
        write_json(pool_path, migrated_pool)

    report = build_report(
        mode="apply" if apply else "dry-run",
        pool_path=pool_path,
        backup_path=backup_path,
        stats=stats,
    )
    write_json(report_path, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair legacy candidate_pool.json for the TMDb-only contract.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Build report without changing legacy candidate_pool.json.")
    mode.add_argument("--apply", action="store_true", help="Backup and rewrite legacy candidate_pool.json.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_migration(apply=args.apply)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
