"""Lazy localized poster enrichment for candidate pool records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from candidates.models.keys import pool_entry_key
from candidates.repositories import pool_repository
from dataset.language import normalize_data_language, tmdb_locale_for_data_language
from dataset.tmdb_localized import localized_blocks_from_tmdb_details


def _localized_poster_available(record: dict | None, data_language: str) -> bool:
    if isinstance(record, dict) is False:
        return False
    localized = record.get("localized") if isinstance(record.get("localized"), dict) else {}
    block = localized.get(normalize_data_language(data_language))
    if isinstance(block, dict) is False:
        return False
    return any(block.get(key) not in (None, "") for key in ("poster_url", "poster_path"))


def _candidate_tmdb_id(candidate: dict | None):
    if isinstance(candidate, dict) is False:
        return None
    if candidate.get("tmdb_id") not in (None, ""):
        return candidate.get("tmdb_id")
    source_query = candidate.get("source_query")
    if isinstance(source_query, dict):
        return source_query.get("tmdb_id")
    return None


def _merge_localized_blocks(candidate: dict, blocks: dict) -> dict:
    updated = deepcopy(candidate)
    localized = updated.setdefault("localized", {})
    if isinstance(localized, dict) is False:
        localized = {}
        updated["localized"] = localized

    for language, block in blocks.items():
        if isinstance(block, dict) is False:
            continue
        normalized = normalize_data_language(language)
        target = localized.setdefault(normalized, {})
        if isinstance(target, dict) is False:
            target = {}
            localized[normalized] = target
        for field_name, value in block.items():
            if value in (None, ""):
                continue
            if field_name in {"poster_path", "poster_url"} or target.get(field_name) in (None, ""):
                target[field_name] = value
    return updated


def _find_pool_key(pool: dict, candidate: dict) -> str | None:
    explicit = candidate.get("pool_entry_key")
    if explicit not in (None, "") and str(explicit) in pool:
        return str(explicit)
    identity = pool_entry_key(candidate)
    return identity if identity in pool else None


def ensure_candidate_localized_poster(
    candidate: dict,
    data_language: str = "ru",
    *,
    details_func=None,
    persist: bool = True,
) -> tuple[dict, bool]:
    """Fetch and persist localized poster metadata for one candidate on demand."""
    if isinstance(candidate, dict) is False:
        return candidate, False

    language = normalize_data_language(data_language)
    if _localized_poster_available(candidate, language):
        return candidate, False

    tmdb_id = _candidate_tmdb_id(candidate)
    if tmdb_id in (None, ""):
        return candidate, False

    from apis import tmdb_api

    details_func = details_func or tmdb_api.get_tv_details
    details = details_func(
        int(tmdb_id),
        language=tmdb_locale_for_data_language(language),
        append_to_response=tmdb_api.DEFAULT_TV_DETAIL_APPENDS,
    )
    blocks = localized_blocks_from_tmdb_details(details, current_language=language)
    if _localized_poster_available({"localized": blocks}, language) is False:
        return candidate, False

    updated_candidate = _merge_localized_blocks(candidate, blocks)
    if persist is False:
        return updated_candidate, True

    try:
        pool = pool_repository.load_candidate_pool()
        key = _find_pool_key(pool, candidate)
        if key is not None:
            pool[key] = _merge_localized_blocks(
                pool[key] if isinstance(pool[key], dict) else {},
                blocks,
            )
            pool_repository.save_candidate_pool(pool)
            return pool[key], True
    except Exception:
        return updated_candidate, True

    return updated_candidate, True
