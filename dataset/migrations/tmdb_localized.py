"""Backfill localized data from TMDb without renaming legacy records."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shutil
from typing import Any

from apis import tmdb_api
from config import constant
from tools.migrations import legacy_paths
from dataset.language import normalize_data_language, tmdb_locale_for_data_language


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _clean_text(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text if text else None


def _translation_data_for_language(details: dict[str, Any], language: str) -> dict[str, Any]:
    normalized = normalize_data_language(language)
    locale = tmdb_locale_for_data_language(normalized)
    expected_country = locale.split("-", 1)[1].upper() if "-" in locale else ""
    expected_language = locale.split("-", 1)[0].lower()
    translations = details.get("translations", {}).get("translations")
    if isinstance(translations, list) is False:
        return {}

    fallback_data: dict[str, Any] = {}
    for translation in translations:
        if isinstance(translation, dict) is False:
            continue
        if str(translation.get("iso_639_1") or "").lower() != expected_language:
            continue
        data = translation.get("data")
        if isinstance(data, dict) is False:
            continue
        if str(translation.get("iso_3166_1") or "").upper() == expected_country:
            return data
        if not fallback_data:
            fallback_data = data
    return fallback_data


def _read_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=4)
        file.write("\n")


def backup_path_for(path: Path, timestamp: str) -> Path:
    return path.with_name(f"{path.stem}.before_tmdb_localized.{timestamp}{path.suffix}")


def _backup_existing(path: Path, timestamp: str) -> Path:
    backup_path = backup_path_for(path, timestamp)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path


def localized_block_from_tmdb_details(details: dict[str, Any], language: str | None = None) -> dict[str, str]:
    """Extract display strings from TMDb Details response for the requested locale."""
    block: dict[str, str] = {}
    translation_data = _translation_data_for_language(details, language) if language is not None else {}
    title = _clean_text(translation_data.get("name") or translation_data.get("title"))
    if title is None:
        title = _clean_text(details.get("name") or details.get("title"))
    overview = _clean_text(translation_data.get("overview"))
    if overview is None:
        overview = _clean_text(details.get("overview"))
    if title is not None:
        block["title"] = title
    if overview is not None:
        block["overview"] = overview
    return block


def merge_localized_block(record: dict, language: str, block: dict[str, str]) -> tuple[dict, bool]:
    """Merge localized TMDb strings into a record, preserving existing values."""
    if isinstance(record, dict) is False:
        return record, False
    normalized = normalize_data_language(language)
    updated = deepcopy(record)
    localized = updated.setdefault("localized", {})
    if isinstance(localized, dict) is False:
        localized = {}
        updated["localized"] = localized
    language_block = localized.setdefault(normalized, {})
    if isinstance(language_block, dict) is False:
        language_block = {}
        localized[normalized] = language_block

    for field_name in ("title", "overview"):
        value = _clean_text(block.get(field_name))
        if value is None:
            continue
        if _clean_text(language_block.get(field_name)) is None:
            language_block[field_name] = value

    return updated, updated != record


def backfill_mapping_from_tmdb(
    records: dict,
    *,
    data_language: str = "en",
    details_func=None,
    force_refresh: bool = False,
    limit: int | None = None,
) -> tuple[dict, dict]:
    """Backfill localized fields for mapping values with tmdb_id."""
    normalized = normalize_data_language(data_language)
    tmdb_locale = tmdb_locale_for_data_language(normalized)
    details_func = details_func or tmdb_api.get_tv_details
    updated_records = {}
    changed_count = 0
    requested_count = 0
    skipped_count = 0
    errors: list[dict[str, Any]] = []

    for key, record in records.items():
        if limit is not None and requested_count >= int(limit):
            updated_records[key] = record
            skipped_count += 1
            continue
        if isinstance(record, dict) is False or record.get("tmdb_id") in (None, ""):
            updated_records[key] = record
            skipped_count += 1
            continue

        try:
            requested_count += 1
            details = details_func(
                int(record["tmdb_id"]),
                language=tmdb_locale,
                append_to_response=tmdb_api.DEFAULT_TV_DETAIL_APPENDS,
                force_refresh=force_refresh,
            )
            localized_block = localized_block_from_tmdb_details(details, normalized)
            updated, changed = merge_localized_block(record, normalized, localized_block)
        except Exception as error:  # noqa: BLE001 - migration should report and continue.
            updated = record
            changed = False
            errors.append({"key": str(key), "tmdb_id": record.get("tmdb_id"), "error": str(error)})

        updated_records[key] = updated
        if changed:
            changed_count += 1

    report = {
        "data_language": normalized,
        "tmdb_locale": tmdb_locale,
        "requested_records": requested_count,
        "changed_records": changed_count,
        "skipped_records": skipped_count,
        "errors": errors,
    }
    return updated_records, report


def backfill_watched_meta_from_tmdb(
    *,
    meta_path: str | Path | None = None,
    data_language: str = "en",
    dry_run: bool = False,
    force_refresh: bool = False,
    limit: int | None = None,
    timestamp: str | None = None,
    details_func=None,
) -> dict:
    """Backfill watched meta localized strings from TMDb Details."""
    path = Path(meta_path or legacy_paths.watched_meta_json(constant.APP_DATA_DIR))
    records = _read_json(path)
    updated, report = backfill_mapping_from_tmdb(
        records,
        data_language=data_language,
        details_func=details_func,
        force_refresh=force_refresh,
        limit=limit,
    )
    backup_path = None
    written = False
    if report["changed_records"] > 0 and dry_run is False:
        stamp = timestamp or _timestamp()
        backup_path = _backup_existing(path, stamp)
        _write_json(path, updated)
        written = True

    return {
        **report,
        "path": str(path),
        "backup_path": str(backup_path) if backup_path is not None else None,
        "dry_run": dry_run,
        "written": written,
    }


def backfill_candidate_pool_from_tmdb(
    *,
    pool_path: str | Path | None = None,
    data_language: str = "en",
    dry_run: bool = False,
    force_refresh: bool = False,
    limit: int | None = None,
    timestamp: str | None = None,
    details_func=None,
) -> dict:
    """Backfill candidate pool localized strings from TMDb Details."""
    path = Path(pool_path or legacy_paths.candidate_pool_json(constant.APP_DATA_DIR))
    records = _read_json(path)
    updated, report = backfill_mapping_from_tmdb(
        records,
        data_language=data_language,
        details_func=details_func,
        force_refresh=force_refresh,
        limit=limit,
    )
    backup_path = None
    written = False
    if report["changed_records"] > 0 and dry_run is False:
        stamp = timestamp or _timestamp()
        backup_path = _backup_existing(path, stamp)
        _write_json(path, updated)
        written = True

    return {
        **report,
        "path": str(path),
        "backup_path": str(backup_path) if backup_path is not None else None,
        "dry_run": dry_run,
        "written": written,
    }


__all__ = [
    "backfill_candidate_pool_from_tmdb",
    "backfill_mapping_from_tmdb",
    "backfill_watched_meta_from_tmdb",
    "backup_path_for",
    "localized_block_from_tmdb_details",
    "merge_localized_block",
]
