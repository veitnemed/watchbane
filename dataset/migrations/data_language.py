"""Backward-compatible localized data migration."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shutil
from typing import Any

from config import constant
from tools.migrations import legacy_paths
from dataset.language import build_localized_block_from_legacy


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_path_for(path: Path, timestamp: str) -> Path:
    """Return migration backup path next to the source file."""
    return path.with_name(f"{path.stem}.before_data_language.{timestamp}{path.suffix}")


def _read_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=4)
        file.write("\n")


def _clean_text(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text if text else None


def _set_if_missing(block: dict, language: str, field: str, value) -> None:
    text = _clean_text(value)
    if text is None:
        return
    language_block = block.setdefault(language, {})
    if _clean_text(language_block.get(field)) is None:
        language_block[field] = text


def _first_text(record: dict, *field_names: str) -> str | None:
    for field_name in field_names:
        text = _clean_text(record.get(field_name))
        if text is not None:
            return text
    return None


def migrate_watched_record(record: dict) -> tuple[dict, bool]:
    """Add localized block to one watched dataset/meta record."""
    if isinstance(record, dict) is False:
        return record, False
    updated = deepcopy(record)
    localized = build_localized_block_from_legacy(updated, default_language="ru")
    if len(localized) > 0:
        updated["localized"] = localized
    return updated, updated != record


def migrate_candidate_record(record: dict) -> tuple[dict, bool]:
    """Add localized block to one candidate-pool record."""
    if isinstance(record, dict) is False:
        return record, False
    updated = deepcopy(record)
    localized = build_localized_block_from_legacy(updated, default_language="ru")
    _set_if_missing(
        localized,
        "en",
        "title",
        _first_text(
            updated,
            "original_title",
            "original_name",
            "enName",
            "alternative_title",
            "alternativeName",
            "title",
            "name",
        ),
    )
    if len(localized) > 0:
        updated["localized"] = localized
    return updated, updated != record


def _migrate_mapping(payload: dict, record_migrator) -> tuple[dict, int]:
    updated = {}
    changed_count = 0
    for key, record in payload.items():
        migrated_record, changed = record_migrator(record)
        updated[key] = migrated_record
        if changed:
            changed_count += 1
    return updated, changed_count


def _migrate_sequence(payload: list, record_migrator) -> tuple[list, int]:
    updated = []
    changed_count = 0
    for record in payload:
        migrated_record, changed = record_migrator(record)
        updated.append(migrated_record)
        if changed:
            changed_count += 1
    return updated, changed_count


def migrate_payload(payload, record_migrator) -> tuple[Any, int]:
    """Migrate dict/list payload while preserving mapping keys."""
    if isinstance(payload, dict):
        return _migrate_mapping(payload, record_migrator)
    if isinstance(payload, list):
        return _migrate_sequence(payload, record_migrator)
    return payload, 0


def _backup_existing(path: Path, timestamp: str) -> Path | None:
    if path.exists() is False:
        return None
    backup_path = backup_path_for(path, timestamp)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path


def _migrate_file(
    path: Path,
    record_migrator,
    *,
    dry_run: bool,
    timestamp: str,
) -> dict:
    if path.exists() is False:
        return {
            "path": str(path),
            "exists": False,
            "changed_records": 0,
            "backup_path": None,
            "written": False,
        }

    original = _read_json(path)
    migrated, changed_count = migrate_payload(original, record_migrator)
    written = False
    backup_path = None
    if changed_count > 0 and dry_run is False:
        backup_path = _backup_existing(path, timestamp)
        _write_json(path, migrated)
        written = True

    return {
        "path": str(path),
        "exists": True,
        "changed_records": changed_count,
        "backup_path": str(backup_path) if backup_path is not None else None,
        "written": written,
    }


def migrate_data_language_files(
    *,
    dataset_path: str | Path | None = None,
    meta_path: str | Path | None = None,
    pool_path: str | Path | None = None,
    dry_run: bool = False,
    timestamp: str | None = None,
) -> dict:
    """Migrate watched dataset/meta and candidate pool JSON files."""
    stamp = timestamp or _timestamp()
    watched_dataset_path = Path(dataset_path or legacy_paths.watched_titles_json(constant.APP_DATA_DIR))
    watched_meta_path = Path(meta_path or legacy_paths.watched_meta_json(constant.APP_DATA_DIR))
    candidate_pool_path = Path(pool_path or legacy_paths.candidate_pool_json(constant.APP_DATA_DIR))

    files = {
        "watched_dataset": _migrate_file(
            watched_dataset_path,
            migrate_watched_record,
            dry_run=dry_run,
            timestamp=stamp,
        ),
        "watched_meta": _migrate_file(
            watched_meta_path,
            migrate_watched_record,
            dry_run=dry_run,
            timestamp=stamp,
        ),
        "candidate_pool": _migrate_file(
            candidate_pool_path,
            migrate_candidate_record,
            dry_run=dry_run,
            timestamp=stamp,
        ),
    }
    return {
        "timestamp": stamp,
        "dry_run": dry_run,
        "files": files,
        "changed_records": sum(item["changed_records"] for item in files.values()),
    }


__all__ = [
    "backup_path_for",
    "migrate_candidate_record",
    "migrate_data_language_files",
    "migrate_payload",
    "migrate_watched_record",
]
