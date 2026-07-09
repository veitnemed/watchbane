"""One-time migration of watched raw_scores to the TMDb-only schema."""

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

from common import format_score
from config import constant, scheme
from storage.normalize import normalize_raw_scores

REPORT_PATH = ROOT_DIR / "data" / "diagnostics" / "watched_raw_scores_tmdb_only_migration_report.json"
LEGACY_RAW_SCORE_FIELDS = {"kp_score", "kp_votes", "imdb_score", "imdb_votes"}


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
    return path.with_name(f"{path.stem}.before_tmdb_raw_scores.{timestamp}{path.suffix}")


def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def _strip_raw_scores(raw_scores: dict[str, Any]) -> tuple[dict[str, Any], int]:
    stripped_count = sum(1 for field_name in LEGACY_RAW_SCORE_FIELDS if field_name in raw_scores)
    return normalize_raw_scores(raw_scores), stripped_count


def migrate_watched_raw_scores(
    dataset: dict[str, Any],
    meta: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    migrated_dataset = dict(dataset if isinstance(dataset, dict) else {})
    migrated_meta = dict(meta if isinstance(meta, dict) else {})
    stats = {
        "total_watched": len(migrated_dataset),
        "dataset_records_migrated": 0,
        "meta_records_migrated": 0,
        "stripped_legacy_fields": 0,
    }

    for title, movie in list(migrated_dataset.items()):
        if isinstance(movie, dict) is False:
            continue
        raw_scores = dict(movie.get(scheme.RAW_SCORES) or {})
        normalized_raw, stripped_count = _strip_raw_scores(raw_scores)
        if stripped_count > 0 or raw_scores != normalized_raw:
            updated_movie = dict(movie)
            main_info = dict(updated_movie.get(scheme.MAIN_INFO) or {})
            updated_movie[scheme.RAW_SCORES] = normalized_raw
            updated_movie["computed_scores"] = format_score.raw_to_struct(normalized_raw, main_info)
            migrated_dataset[title] = updated_movie
            stats["dataset_records_migrated"] += 1
            stats["stripped_legacy_fields"] += stripped_count

    for title, meta_obj in list(migrated_meta.items()):
        if isinstance(meta_obj, dict) is False:
            continue
        raw_scores = dict(meta_obj.get(scheme.RAW_SCORES) or {})
        normalized_raw, stripped_count = _strip_raw_scores(raw_scores)
        if stripped_count > 0 or raw_scores != normalized_raw:
            updated_meta = dict(meta_obj)
            updated_meta[scheme.RAW_SCORES] = normalized_raw
            migrated_meta[title] = updated_meta
            stats["meta_records_migrated"] += 1
            stats["stripped_legacy_fields"] += stripped_count

    return migrated_dataset, migrated_meta, stats


def run_migration(*, apply: bool, report_path: Path = REPORT_PATH) -> dict[str, Any]:
    dataset_file = watched_path()
    meta_file = meta_path()
    dataset = read_json(dataset_file)
    meta = read_json(meta_file)
    migrated_dataset, migrated_meta, stats = migrate_watched_raw_scores(dataset, meta)

    backup_paths = {}
    if apply:
        timestamp = _timestamp()
        dataset_backup = backup_path_for(dataset_file, timestamp)
        meta_backup = backup_path_for(meta_file, timestamp)
        if dataset_file.exists():
            shutil.copy2(dataset_file, dataset_backup)
        else:
            write_json(dataset_backup, dataset)
        if meta_file.exists():
            shutil.copy2(meta_file, meta_backup)
        else:
            write_json(meta_backup, meta)
        write_json(dataset_file, migrated_dataset)
        write_json(meta_file, migrated_meta)
        backup_paths = {"dataset": str(dataset_backup), "meta": str(meta_backup)}

    report = {
        "mode": "apply" if apply else "dry-run",
        "dataset_path": str(dataset_file),
        "meta_path": str(meta_file),
        "backup_paths": backup_paths,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        **stats,
    }
    write_json(report_path, report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate watched raw_scores to the TMDb-only schema.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_migration(apply=args.apply)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
