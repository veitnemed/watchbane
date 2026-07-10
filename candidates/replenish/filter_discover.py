"""TMDb Discover params for filter-driven replenish buckets."""

from __future__ import annotations

from datetime import date
from typing import Any

from dataset.language import tmdb_locale_for_data_language

NO_VOTE_RATING_DISCOVER_KEYS = (
    "vote_count.gte",
    "vote_average.gte",
    "vote_count_gte",
    "vote_average_gte",
)
BROAD_ORIGIN_FALLBACK_KEYS = (
    "fallback",
    "broad_origin",
    "broad_origin_fallback",
    "without_origin_country",
)
CLASSIC_START_YEAR = 2005
CLASSIC_END_YEAR = 2021
NEW_START_YEAR = 2022


def _safe_page(page: Any) -> int:
    try:
        value = int(page)
    except (TypeError, ValueError):
        value = 1
    return max(1, value)


def _genre_value(values: Any, *, separator: str) -> str | None:
    if not isinstance(values, (list, tuple, set)):
        return None
    result: list[str] = []
    for value in values:
        try:
            genre_id = int(value)
        except (TypeError, ValueError):
            continue
        text = str(genre_id)
        if text not in result:
            result.append(text)
    return separator.join(result) if result else None


def _intent_dict(intent: dict[str, Any] | None) -> dict[str, Any]:
    return dict(intent or {})


def _language(intent: dict[str, Any]) -> str:
    return tmdb_locale_for_data_language(intent.get("data_language") or intent.get("ui_language") or "ru")


def _year_bounds(intent: dict[str, Any], bucket: dict[str, Any]) -> tuple[int | None, int | None]:
    year_min = bucket.get("year_min")
    year_max = bucket.get("year_max")
    if year_min is None:
        year_min = intent.get("year_min")
    if year_max is None:
        year_max = intent.get("year_max")

    release_preference = intent.get("release_preference")
    if year_min is None and year_max is None:
        if release_preference == "new":
            year_min = NEW_START_YEAR
            year_max = date.today().year
        elif release_preference == "classic":
            year_min = CLASSIC_START_YEAR
            year_max = CLASSIC_END_YEAR

    try:
        normalized_min = int(year_min) if year_min is not None else None
    except (TypeError, ValueError):
        normalized_min = None
    try:
        normalized_max = int(year_max) if year_max is not None else None
    except (TypeError, ValueError):
        normalized_max = None
    if normalized_min is not None and normalized_max is not None and normalized_min > normalized_max:
        normalized_min, normalized_max = normalized_max, normalized_min
    return normalized_min, normalized_max


def _date_field_prefix(media_type: str) -> str:
    return "first_air_date" if media_type == "tv" else "primary_release_date"


def build_filter_discover_params(
    bucket: dict[str, Any],
    page: int,
    *,
    intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build safe TMDb Discover params for one replenish plan bucket."""
    normalized_intent = _intent_dict(intent)
    media_type = str(bucket.get("media_type") or normalized_intent.get("media_type") or "movie")
    year_min, year_max = _year_bounds(normalized_intent, bucket)
    date_prefix = _date_field_prefix(media_type)
    params: dict[str, Any] = {
        "include_adult": False,
        "sort_by": "popularity.desc",
        "language": _language(normalized_intent),
        "page": _safe_page(page),
    }

    country = bucket.get("with_origin_country") or bucket.get("country")
    if country not in (None, ""):
        params["with_origin_country"] = str(country).strip().upper()

    if year_min is not None:
        params[f"{date_prefix}.gte"] = f"{year_min:04d}-01-01"
    if year_max is not None:
        params[f"{date_prefix}.lte"] = f"{year_max:04d}-12-31"

    with_genres = _genre_value(bucket.get("include_tmdb_genres"), separator="|")
    without_genres = _genre_value(bucket.get("exclude_tmdb_genres"), separator=",")
    if with_genres is not None:
        params["with_genres"] = with_genres
    if without_genres is not None:
        params["without_genres"] = without_genres

    return {
        key: value
        for key, value in params.items()
        if key not in NO_VOTE_RATING_DISCOVER_KEYS and key not in BROAD_ORIGIN_FALLBACK_KEYS
    }


def discover_params_have_vote_rating_filters(params: dict[str, Any]) -> bool:
    """Return True if forbidden vote/rating filters are present."""
    keys = set(params)
    return any(key in keys for key in NO_VOTE_RATING_DISCOVER_KEYS)


def discover_params_have_broad_origin_fallback(params: dict[str, Any]) -> bool:
    """Return True if broad-origin fallback markers are present."""
    keys = set(params)
    return any(key in keys for key in BROAD_ORIGIN_FALLBACK_KEYS)
