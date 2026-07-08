"""Storage identity helpers for candidate pool records."""

from __future__ import annotations

from typing import Any

from candidates.models.keys import pool_entry_key
from dataset.models.media_type import normalize_media_type


def coerce_tmdb_id(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def candidate_tmdb_identity(candidate: dict[str, Any]) -> tuple[str, int] | None:
    tmdb_id = coerce_tmdb_id(candidate.get("tmdb_id"))
    if tmdb_id is None:
        return None
    return normalize_media_type(candidate.get("media_type")), tmdb_id


def build_tmdb_id_index(pool: dict[str, Any]) -> dict[tuple[str, int], str]:
    index: dict[tuple[str, int], str] = {}
    for key, candidate in (pool or {}).items():
        if isinstance(candidate, dict) is False:
            continue
        identity = candidate_tmdb_identity(candidate)
        if identity is None or identity in index:
            continue
        index[identity] = key
    return index


def find_candidate_storage_match(
    pool: dict[str, Any],
    candidate: dict[str, Any],
    *,
    tmdb_id_index: dict[tuple[str, int], str] | None = None,
) -> tuple[str | None, str | None]:
    """Finds existing candidate by primary media_type/tmdb_id, then title/year storage key."""
    tmdb_identity = candidate_tmdb_identity(candidate)
    if tmdb_identity is not None:
        index = tmdb_id_index if tmdb_id_index is not None else build_tmdb_id_index(pool)
        matched_key = index.get(tmdb_identity)
        if matched_key is not None:
            return matched_key, "tmdb_id"

    fallback_key = pool_entry_key(candidate)
    if fallback_key and fallback_key != "|" and fallback_key in pool:
        return fallback_key, "title_year"
    return None, None


def candidate_storage_key(candidate: dict[str, Any]) -> str:
    return pool_entry_key(candidate)
