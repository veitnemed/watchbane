"""Build bounded replenish plans from normalized filter intent."""

from __future__ import annotations

from typing import Any

from candidates.onboarding.autofill import TMDB_ANIMATION_GENRE_ID, TV_JUNK_GENRE_IDS, genre_ids_for_groups
from candidates.replenish.compatibility import resolve_filter_replenish_compatibility
from candidates.replenish.filter_intent import (
    ANIMATION_MODE_ANIMATION_ONLY,
    ANIMATION_MODE_LIVE_ACTION_ONLY,
    MEDIA_TYPE_BOTH,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TV,
    FilterReplenishIntent,
)
from candidates.sources.tmdb.genre_options import (
    EXCLUDE_MOVIE_GENRE_OPTIONS,
    EXCLUDE_TV_GENRE_OPTIONS,
    INCLUDE_MOVIE_GENRE_OPTIONS,
    INCLUDE_TV_GENRE_OPTIONS,
)

DEFAULT_MAX_PAGES_PER_BUCKET = 3
DEFAULT_DETAILS_LIMIT_MULTIPLIER = 2
MAX_DETAILS_LIMIT = 60


def _as_intent(intent: FilterReplenishIntent | dict[str, Any]) -> FilterReplenishIntent:
    if isinstance(intent, FilterReplenishIntent):
        return intent
    return FilterReplenishIntent.from_dict(intent)


def _media_values(media_type: str | None) -> list[str]:
    if media_type == MEDIA_TYPE_MOVIE:
        return [MEDIA_TYPE_MOVIE]
    if media_type == MEDIA_TYPE_TV:
        return [MEDIA_TYPE_TV]
    return [MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV]


def _quota_split(total: int, bucket_count: int) -> list[int]:
    if bucket_count <= 0:
        return []
    if total <= 0:
        return [0 for _ in range(bucket_count)]
    base = total // bucket_count
    remainder = total % bucket_count
    return [base + (1 if index < remainder else 0) for index in range(bucket_count)]


def _normalize_genre_name(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .casefold()
        .replace("&", "and")
        .replace("-", " ")
        .replace("_", " ")
    )


def _genre_option_index(media_type: str) -> dict[str, int]:
    options = (
        INCLUDE_TV_GENRE_OPTIONS + EXCLUDE_TV_GENRE_OPTIONS
        if media_type == MEDIA_TYPE_TV
        else INCLUDE_MOVIE_GENRE_OPTIONS + EXCLUDE_MOVIE_GENRE_OPTIONS
    )
    index: dict[str, int] = {}
    for option in options:
        genre_id = int(option["id"])
        for key in (option.get("tmdb_name"), option.get("label"), option.get("id")):
            normalized = _normalize_genre_name(key)
            if normalized:
                index[normalized] = genre_id
    return index


def _genre_ids_from_labels(labels: list[str], media_type: str) -> list[int]:
    option_index = _genre_option_index(media_type)
    result: list[int] = []
    for label in labels or []:
        raw_text = str(label or "").strip()
        if raw_text == "":
            continue
        try:
            genre_id = int(raw_text)
        except ValueError:
            genre_id = option_index.get(_normalize_genre_name(raw_text))
        if genre_id is None or genre_id in result:
            continue
        result.append(genre_id)
    return result


def _append_unique(values: list[int], additions: list[int] | tuple[int, ...]) -> list[int]:
    for value in additions:
        genre_id = int(value)
        if genre_id not in values:
            values.append(genre_id)
    return values


def _planned_genres(intent: FilterReplenishIntent, media_type: str) -> tuple[list[int], list[int]]:
    include_genres: list[int] = []
    exclude_genres: list[int] = []

    _append_unique(include_genres, genre_ids_for_groups(intent.genre_groups, media_type))
    _append_unique(include_genres, _genre_ids_from_labels(intent.include_genres, media_type))
    _append_unique(exclude_genres, _genre_ids_from_labels(intent.exclude_genres, media_type))

    if media_type == MEDIA_TYPE_TV:
        _append_unique(exclude_genres, TV_JUNK_GENRE_IDS)

    if intent.animation_mode == ANIMATION_MODE_ANIMATION_ONLY:
        include_genres = [genre_id for genre_id in include_genres if genre_id != TMDB_ANIMATION_GENRE_ID]
        exclude_genres = [genre_id for genre_id in exclude_genres if genre_id != TMDB_ANIMATION_GENRE_ID]
        include_genres.insert(0, TMDB_ANIMATION_GENRE_ID)

    if intent.animation_mode == ANIMATION_MODE_LIVE_ACTION_ONLY:
        include_genres = [genre_id for genre_id in include_genres if genre_id != TMDB_ANIMATION_GENRE_ID]
        _append_unique(exclude_genres, (TMDB_ANIMATION_GENRE_ID,))

    return include_genres, exclude_genres


def _details_limit(target_add_count: int) -> int:
    return min(MAX_DETAILS_LIMIT, max(target_add_count, target_add_count * DEFAULT_DETAILS_LIMIT_MULTIPLIER))


def build_filter_replenish_plan(
    intent: FilterReplenishIntent | dict[str, Any],
    existing_pool_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Translate filter intent into bounded country/media buckets without HTTP requests."""
    normalized = _as_intent(intent)
    compatibility = resolve_filter_replenish_compatibility(normalized)
    countries: list[str | None] = list(normalized.countries) if normalized.countries else [None]
    media_values = _media_values(normalized.media_type)
    pairs = [(country, media_type) for country in countries for media_type in media_values]
    quotas = _quota_split(normalized.target_add_count, len(pairs))

    buckets: list[dict[str, Any]] = []
    for index, ((country, media_type), quota) in enumerate(zip(pairs, quotas), start=1):
        if quota <= 0:
            continue
        include_genres, exclude_genres = _planned_genres(normalized, media_type)
        country_key = country or "any"
        buckets.append({
            "bucket_id": f"{country_key}:{media_type}:{index}",
            "quota": quota,
            "country": country,
            "media_type": media_type,
            "with_origin_country": country,
            "include_tmdb_genres": include_genres,
            "exclude_tmdb_genres": exclude_genres,
            "year_min": normalized.year_min,
            "year_max": normalized.year_max,
            "max_pages": DEFAULT_MAX_PAGES_PER_BUCKET,
            "details_limit": _details_limit(quota),
        })

    country_plan: dict[str, int] = {}
    media_plan: dict[str, int] = {}
    include_tmdb_genres: list[int] = []
    exclude_tmdb_genres: list[int] = []
    for bucket in buckets:
        country_key = bucket["country"] or "any"
        media_key = bucket["media_type"]
        country_plan[country_key] = country_plan.get(country_key, 0) + int(bucket["quota"])
        media_plan[media_key] = media_plan.get(media_key, 0) + int(bucket["quota"])
        _append_unique(include_tmdb_genres, bucket["include_tmdb_genres"])
        _append_unique(exclude_tmdb_genres, bucket["exclude_tmdb_genres"])

    return {
        "target_add_count": normalized.target_add_count,
        "buckets": buckets,
        "bucket_count": len(buckets),
        "country_plan": country_plan,
        "media_plan": media_plan,
        "include_tmdb_genres": include_tmdb_genres,
        "exclude_tmdb_genres": exclude_tmdb_genres,
        "animation_mode": normalized.animation_mode,
        "compatibility_warnings": compatibility["warnings"],
        "compatibility_blocking_conflicts": compatibility["blocking_conflicts"],
        "can_run": compatibility["can_run"],
        "max_pages_per_bucket": DEFAULT_MAX_PAGES_PER_BUCKET,
        "details_limit": _details_limit(normalized.target_add_count),
        "broad_origin_allowed": False,
        "intent": normalized.to_dict(),
        "existing_pool_summary": dict(existing_pool_summary or {}),
    }
