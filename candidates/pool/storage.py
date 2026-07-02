"""Storage identity helpers for candidate pool records."""

from __future__ import annotations

from typing import Any

from candidates.models.keys import pool_entry_key


def coerce_tmdb_id(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_tmdb_id_index(pool: dict[str, Any]) -> dict[int, str]:
    index: dict[int, str] = {}
    for key, candidate in (pool or {}).items():
        if isinstance(candidate, dict) is False:
            continue
        tmdb_id = coerce_tmdb_id(candidate.get("tmdb_id"))
        if tmdb_id is None or tmdb_id in index:
            continue
        index[tmdb_id] = key
    return index


def find_candidate_storage_match(pool: dict[str, Any], candidate: dict[str, Any]) -> tuple[str | None, str | None]:
    """Finds existing candidate by primary tmdb_id, then title/year storage key."""
    tmdb_id = coerce_tmdb_id(candidate.get("tmdb_id"))
    if tmdb_id is not None:
        matched_key = build_tmdb_id_index(pool).get(tmdb_id)
        if matched_key is not None:
            return matched_key, "tmdb_id"

    fallback_key = pool_entry_key(candidate)
    if fallback_key and fallback_key != "|" and fallback_key in pool:
        return fallback_key, "title_year"
    return None, None


def candidate_storage_key(candidate: dict[str, Any]) -> str:
    return pool_entry_key(candidate)
