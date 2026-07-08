"""Deduplication and watched filtering for TMDb Discover results."""

from __future__ import annotations

from typing import Any

from candidates.pool.dataset_overlap import build_dataset_title_keys
from candidates.pool.watched_cleanup import build_watched_signatures, is_watched_candidate
from apis import tmdb_api as api_tmdb
from dataset.models.media_type import MEDIA_TYPE_MOVIE, normalize_media_type


def deduplicate_discover_results(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    duplicates = 0
    for item in items:
        tmdb_id = item.get("id")
        if tmdb_id in (None, ""):
            continue
        tmdb_id = int(tmdb_id)
        if tmdb_id in seen:
            duplicates += 1
            continue
        seen.add(tmdb_id)
        unique.append(item)
    return unique, duplicates


def sort_discover_for_details(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            -(item.get("vote_count") or 0),
            -(item.get("vote_average") or 0),
            -(item.get("popularity") or 0),
            item.get("id") or 0,
        ),
    )


def _discover_candidate_for_watched(item: dict[str, Any], media_type: str) -> dict[str, Any]:
    if media_type == MEDIA_TYPE_MOVIE:
        return {
            "media_type": MEDIA_TYPE_MOVIE,
            "tmdb_id": item.get("id"),
            "title": item.get("title") or item.get("original_title") or "",
            "alternative_title": item.get("original_title") or "",
            "year": api_tmdb.get_year(item.get("release_date")),
            "release_date": item.get("release_date"),
        }
    return {
        "media_type": media_type,
        "tmdb_id": item.get("id"),
        "title": item.get("name") or item.get("original_name") or "",
        "alternative_title": item.get("original_name") or "",
        "year": api_tmdb.get_year(item.get("first_air_date")),
        "first_air_date": item.get("first_air_date"),
    }


def remove_watched_discover(
    items: list[dict[str, Any]],
    media_type: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    normalized_media_type = normalize_media_type(media_type)
    try:
        watched_signatures = build_watched_signatures()
        dataset_title_keys = build_dataset_title_keys()
    except Exception:
        watched_signatures = set()
        dataset_title_keys = set()

    if not watched_signatures and not dataset_title_keys:
        return items, 0

    filtered: list[dict[str, Any]] = []
    skipped = 0
    for item in items:
        candidate = _discover_candidate_for_watched(item, normalized_media_type)
        if is_watched_candidate(
            candidate,
            watched_signatures,
            dataset_title_keys,
        ):
            skipped += 1
            continue
        filtered.append(item)
    return filtered, skipped
