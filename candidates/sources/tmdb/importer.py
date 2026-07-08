"""TMDb result import helpers for the common candidate pool."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.models.schema import EXTERNAL_RATING_FIELDS, normalize_candidate_for_storage, strip_external_rating_fields
from candidates.pool.dataset_overlap import build_dataset_title_keys
from candidates.pool.normalization import normalize_storage_pool
from candidates.pool.storage import (
    build_tmdb_id_index,
    candidate_storage_key,
    candidate_tmdb_identity,
    find_candidate_storage_match,
)
from candidates.pool.watched_cleanup import build_watched_signatures, is_watched_candidate
from candidates.repositories.criteria_repository import load_candidate_criteria, save_named_criteria
from candidates.repositories.pool_repository import load_candidate_pool, save_candidate_pool
from candidates.scoring.sort_keys import candidate_sort_score
from candidates.sources.tmdb.scoring import (
    compute_metadata_completeness_score,
    compute_tmdb_final_score,
    compute_tmdb_hidden_gem_score,
    compute_tmdb_quality_score,
)
from candidates.sources.tmdb.output import list_tmdb_result_files


def _count_external_rating_fields(candidate: dict[str, Any]) -> int:
    return sum(1 for field_name in EXTERNAL_RATING_FIELDS if field_name in candidate)


def normalize_tmdb_candidate_for_common_import(candidate: dict[str, Any], criteria_name: str) -> dict[str, Any]:
    normalized = strip_external_rating_fields(candidate)
    normalized.update({
        "title": candidate.get("title"),
        "alternative_title": candidate.get("original_title"),
        "year": candidate.get("year"),
        "first_air_date": candidate.get("first_air_date"),
        "release_date": candidate.get("release_date"),
        "media_type": candidate.get("media_type"),
        "runtime": candidate.get("runtime"),
        "imdb_runtime_minutes": candidate.get("imdb_runtime_minutes"),
        "type": candidate.get("type") or ("movie" if candidate.get("media_type") == "movie" else "series"),
        "description": candidate.get("description") or candidate.get("overview") or "",
        "overview": candidate.get("overview") or candidate.get("description") or "",
        "countries": candidate.get("countries") or candidate.get("tmdb_origin_countries") or candidate.get("origin_country") or [],
        "country_codes": candidate.get("country_codes") or candidate.get("tmdb_country_codes") or candidate.get("origin_country") or [],
        "genres": candidate.get("genres") or candidate.get("genres_tmdb") or [],
        "genre_keys": candidate.get("genre_keys") or [],
        "criteria_name": criteria_name,
        "source": "tmdb",
        "source_provider": "tmdb",
        "source_version": 2,
        "tmdb_id": candidate.get("tmdb_id"),
        "imdb_id": candidate.get("imdb_id"),
        "tmdb_score": candidate.get("tmdb_score") if candidate.get("tmdb_score") is not None else candidate.get("tmdb_rating"),
        "tmdb_votes": candidate.get("tmdb_votes"),
        "tmdb_popularity": candidate.get("tmdb_popularity"),
        "signals": candidate.get("signals") or [],
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    })
    normalized["metadata_completeness_score"] = compute_metadata_completeness_score(normalized)
    normalized["quality_score"] = compute_tmdb_quality_score(normalized)
    normalized["hidden_gem_score"] = compute_tmdb_hidden_gem_score(normalized)
    normalized["final_score"] = compute_tmdb_final_score(normalized)
    return normalize_candidate_for_storage(normalized)


def tmdb_import_default_criteria_name(result: dict[str, Any]) -> str | None:
    candidates = result.get("candidates") or []
    for value in [
        result.get("criteria_name"),
        (result.get("criteria") or {}).get("criteria_name") if isinstance(result.get("criteria"), dict) else None,
        (result.get("settings") or {}).get("criteria_name") if isinstance(result.get("settings"), dict) else None,
    ]:
        text = str(value or "").strip()
        if text:
            return text

    for candidate in candidates:
        value = str(candidate.get("criteria_name") or "").strip()
        if value:
            return value

    country = str(result.get("country") or "").strip()
    mode = str(result.get("mode") or "").strip()
    if country and mode:
        return f"tmdb_{country}_{mode}"
    return None


def resolve_tmdb_import_criteria_name(result: dict[str, Any], criteria_name: str | None = None) -> str:
    return COMMON_POOL_CRITERIA_NAME


def _base_import_stats(read: int, criteria_name: str, pool_size_before: int) -> dict[str, Any]:
    return {
        "ok": True,
        "error": None,
        "read": read,
        "added": 0,
        "updated": 0,
        "watched_skipped": 0,
        "skipped_watched": 0,
        "duplicates": 0,
        "skipped_duplicates": 0,
        "errors": 0,
        "criteria_name": criteria_name,
        "source": "tmdb",
        "source_version": 2,
        "pool_size_before": pool_size_before,
        "pool_size_after": pool_size_before,
        "pool_size": pool_size_before,
        "skipped_existing": 0,
        "incomplete": 0,
        "stripped_external_rating_fields": 0,
    }


def build_tmdb_import_criteria_defaults(criteria_name: str) -> dict[str, Any]:
    """Возвращает безопасный базовый criteria-entry для нового TMDb import."""
    return {
        "criteria_name": criteria_name,
        "count": 0,
        "min_tmdb_score": None,
        "min_tmdb_votes": None,
        "min_year": None,
        "max_year": None,
        "genres": [],
        "excluded_genres": [],
    }


def build_tmdb_import_criteria_metadata(
    *,
    criteria_name: str,
    result_metadata: dict[str, Any],
    result_path: str | Path | None,
    candidate_count: int,
    imported_count: int,
) -> dict[str, Any]:
    """Возвращает metadata-поля, которые TMDb import может безопасно обновлять."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    return {
        "criteria_name": criteria_name,
        "country": result_metadata.get("country"),
        "mode": result_metadata.get("mode"),
        "source": "tmdb",
        "source_version": 2,
        "settings": result_metadata.get("settings") or {},
        "result_file": str(result_path) if result_path is not None else "",
        "updated_at": timestamp,
        "last_imported_at": timestamp,
        "candidate_count": candidate_count,
        "imported_count": imported_count,
    }


def merge_criteria_metadata(existing: dict[str, Any], incoming_metadata: dict[str, Any]) -> dict[str, Any]:
    """Накладывает только metadata-поля поверх существующего criteria, не трогая filters."""
    merged = dict(existing)
    for key, value in incoming_metadata.items():
        merged[key] = value
    return merged


def import_tmdb_candidates_to_common_pool(
    candidates: list[dict[str, Any]],
    criteria_name: str | None = None,
    *,
    result_metadata: dict[str, Any] | None = None,
    result_path: str | Path | None = None,
) -> dict[str, Any]:
    result_metadata = result_metadata or {}
    resolved_criteria_name = resolve_tmdb_import_criteria_name(result_metadata, criteria_name)
    raw_pool = load_candidate_pool()
    pool = normalize_storage_pool(raw_pool)
    tmdb_id_index = build_tmdb_id_index(pool)
    watched_signatures = build_watched_signatures()
    dataset_title_keys = build_dataset_title_keys()
    stats = _base_import_stats(len(candidates), resolved_criteria_name, len(pool))

    for raw_candidate in candidates:
        if isinstance(raw_candidate, dict) is False:
            stats["errors"] += 1
            continue

        stats["stripped_external_rating_fields"] += _count_external_rating_fields(raw_candidate)
        candidate = normalize_tmdb_candidate_for_common_import(raw_candidate, resolved_criteria_name)
        if not candidate.get("title") or not candidate.get("year"):
            stats["errors"] += 1
            continue
        if candidate.get("is_complete") is not True:
            stats["incomplete"] += 1

        if is_watched_candidate(
            candidate,
            watched_signatures,
            dataset_title_keys,
        ):
            stats["watched_skipped"] += 1
            stats["skipped_watched"] += 1
            continue

        matched_key, _match_reason = find_candidate_storage_match(
            pool,
            candidate,
            tmdb_id_index=tmdb_id_index,
        )
        if matched_key is None:
            storage_key = candidate_storage_key(candidate)
            pool[storage_key] = candidate
            tmdb_identity = candidate_tmdb_identity(candidate)
            if tmdb_identity is not None and tmdb_identity not in tmdb_id_index:
                tmdb_id_index[tmdb_identity] = storage_key
            stats["added"] += 1
            continue

        matched_candidate = normalize_candidate_for_storage(pool.get(matched_key) or {})
        stats["stripped_external_rating_fields"] += _count_external_rating_fields(raw_pool.get(matched_key) or {})
        if candidate_sort_score(candidate) > candidate_sort_score(matched_candidate):
            pool[matched_key] = candidate
            tmdb_identity = candidate_tmdb_identity(candidate)
            if tmdb_identity is not None:
                tmdb_id_index[tmdb_identity] = matched_key
            stats["updated"] += 1
        else:
            stats["duplicates"] += 1
            stats["skipped_duplicates"] += 1
            stats["skipped_existing"] += 1

    existing_criteria = load_candidate_criteria().get(resolved_criteria_name) or {}
    criteria_entry = build_tmdb_import_criteria_defaults(resolved_criteria_name)
    criteria_entry.update(existing_criteria if isinstance(existing_criteria, dict) else {})
    criteria_metadata = build_tmdb_import_criteria_metadata(
        criteria_name=resolved_criteria_name,
        result_metadata=result_metadata,
        result_path=result_path,
        candidate_count=len(candidates),
        imported_count=stats["added"] + stats["updated"],
    )
    if criteria_entry.get("count") in (None, 0, ""):
        criteria_entry["count"] = len(candidates)
    save_named_criteria(
        resolved_criteria_name,
        merge_criteria_metadata(criteria_entry, criteria_metadata),
    )
    save_candidate_pool(pool)
    pool_size_after = len(load_candidate_pool())
    stats["pool_size_after"] = pool_size_after
    stats["pool_size"] = pool_size_after
    return stats


def import_tmdb_result_to_common_pool(result_path: str | Path, criteria_name: str | None = None) -> dict[str, Any]:
    result_path = Path(result_path)
    try:
        with open(result_path, "r", encoding="utf-8-sig") as file:
            result = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        return {
            "ok": False,
            "error": str(error),
            "read": 0,
            "added": 0,
            "updated": 0,
            "watched_skipped": 0,
            "skipped_watched": 0,
            "duplicates": 0,
            "skipped_duplicates": 0,
            "errors": 1,
            "criteria_name": str(criteria_name or "").strip(),
            "pool_size_before": 0,
            "pool_size_after": 0,
            "pool_size": 0,
        }

    candidates = result.get("candidates") if isinstance(result, dict) else None
    if isinstance(candidates, list) is False:
        return {
            "ok": False,
            "error": "В файле нет списка candidates.",
            "read": 0,
            "added": 0,
            "updated": 0,
            "watched_skipped": 0,
            "skipped_watched": 0,
            "duplicates": 0,
            "skipped_duplicates": 0,
            "errors": 1,
            "criteria_name": str(criteria_name or "").strip(),
            "pool_size_before": 0,
            "pool_size_after": 0,
            "pool_size": 0,
        }

    return import_tmdb_candidates_to_common_pool(
        candidates,
        criteria_name=criteria_name,
        result_metadata=result if isinstance(result, dict) else {},
        result_path=result_path,
    )
