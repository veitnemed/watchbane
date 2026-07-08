"""Read-only index for skipping already known discover candidates."""

from __future__ import annotations

from typing import Any

from apis import tmdb_api
from candidates.models.keys import normalize_key_part
from candidates.pool.normalization import normalize_storage_pool
from dataset.models.media_type import normalize_media_type


def _coerce_tmdb_id(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_year(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def _title_year_key(title, year) -> str | None:
    normalized_title = normalize_key_part(title)
    normalized_year = _coerce_year(year)
    if normalized_title == "" or normalized_year is None:
        return None
    return f"{normalized_title}|{normalized_year}"


def _media_title_year_key(media_type: str | None, title, year) -> tuple[str, str] | None:
    title_year_key = _title_year_key(title, year)
    if title_year_key is None:
        return None
    return normalize_media_type(media_type), title_year_key


def _candidate_title_year_key(candidate: dict[str, Any]) -> str | None:
    title = (
        candidate.get("title")
        or candidate.get("name")
        or candidate.get("alternative_title")
        or candidate.get("original_title")
        or candidate.get("original_name")
        or ""
    )
    return _title_year_key(title, candidate.get("year"))


def _candidate_media_title_year_key(candidate: dict[str, Any]) -> tuple[str, str] | None:
    return _media_title_year_key(candidate.get("media_type"), _candidate_title(candidate), candidate.get("year"))


def _candidate_title(candidate: dict[str, Any]):
    return (
        candidate.get("title")
        or candidate.get("name")
        or candidate.get("alternative_title")
        or candidate.get("original_title")
        or candidate.get("original_name")
        or ""
    )


def _discover_title(item: dict[str, Any]) -> str:
    return item.get("title") or item.get("name") or item.get("original_title") or item.get("original_name") or ""


def _discover_year(item: dict[str, Any], media_type: str | None = None) -> int | None:
    normalized_media_type = normalize_media_type(media_type)
    date_value = item.get("release_date") if normalized_media_type == "movie" else item.get("first_air_date")
    return tmdb_api.get_year(date_value)


def _discover_media_title_year_key(item: dict[str, Any], media_type: str | None = None) -> tuple[str, str] | None:
    return _media_title_year_key(media_type, _discover_title(item), _discover_year(item, media_type))


def build_existing_candidate_index(pool) -> dict[str, set]:
    """Build tmdb_id and normalized title/year sets from saved pool records."""
    normalized_pool = normalize_storage_pool(pool if isinstance(pool, dict) else {})
    tmdb_ids: set[int] = set()
    tmdb_identities: set[tuple[str, int]] = set()
    title_year_keys: set[str] = set()
    media_title_year_keys: set[tuple[str, str]] = set()

    for candidate in normalized_pool.values():
        if isinstance(candidate, dict) is False:
            continue
        media_type = normalize_media_type(candidate.get("media_type"))
        tmdb_id = _coerce_tmdb_id(candidate.get("tmdb_id"))
        if tmdb_id is not None:
            tmdb_ids.add(tmdb_id)
            tmdb_identities.add((media_type, tmdb_id))

        title_year_key = _candidate_title_year_key(candidate)
        if title_year_key is not None:
            title_year_keys.add(title_year_key)
            media_title_year_key = _candidate_media_title_year_key(candidate)
            if media_title_year_key is not None:
                media_title_year_keys.add(media_title_year_key)

    return {
        "tmdb_ids": tmdb_ids,
        "tmdb_identities": tmdb_identities,
        "title_year_keys": title_year_keys,
        "media_title_year_keys": media_title_year_keys,
    }


def discover_item_existing_reason(item: dict[str, Any], index: dict, media_type: str | None = None) -> str | None:
    """Return the first existing-match reason for one TMDb discover item."""
    normalized_media_type = normalize_media_type(media_type)
    tmdb_id = _coerce_tmdb_id(item.get("id"))
    tmdb_identities = index.get("tmdb_identities") or set()
    if tmdb_id is not None and (normalized_media_type, tmdb_id) in tmdb_identities:
        return "tmdb_id"

    media_title_year_key = _discover_media_title_year_key(item, normalized_media_type)
    if media_title_year_key is not None and media_title_year_key in (index.get("media_title_year_keys") or set()):
        return "title_year"

    return None


def is_discover_item_existing(item: dict[str, Any], index: dict, media_type: str | None = None) -> bool:
    """Return True when a TMDb discover item already exists in the saved pool."""
    return discover_item_existing_reason(item, index, media_type=media_type) is not None


def filter_existing_discover_items(
    items: list[dict[str, Any]],
    index: dict,
    media_type: str | None = None,
) -> list[dict[str, Any]]:
    """Filter discover items already present in saved candidate pool."""
    return [
        item
        for item in items
        if is_discover_item_existing(item, index, media_type=media_type) is False
    ]
