"""TMDb Discover query defaults and filter application."""

from __future__ import annotations

from typing import Any

SERIOUS_GENRES_TMDB = [18, 80, 9648]
WITHOUT_GENRES_TMDB = [16, 10751, 10762, 10763, 10764, 10767]
DEFAULT_VOTE_AVERAGE_GTE = 6.3
DEFAULT_VOTE_COUNT_GTE = 10


def normalize_country_code(value: str | None) -> str:
    return str(value or "").strip().upper()


def is_iso2_country_code(value: str | None) -> bool:
    code = normalize_country_code(value)
    return len(code) == 2 and code.isascii() and code.isalpha()


def discover_defaults(country: str) -> dict[str, Any]:
    country = normalize_country_code(country)
    params: dict[str, Any] = {
        "country": country,
        "vote_average_gte": DEFAULT_VOTE_AVERAGE_GTE,
        "vote_count_gte": DEFAULT_VOTE_COUNT_GTE,
        "language": "ru-RU",
        "sort_by": "vote_count.desc",
    }
    if country == "KR":
        params["with_original_language"] = "ko"
    return params


def normalize_optional_tmdb_genre_filter(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def apply_discover_filters(
    query: dict[str, Any],
    *,
    year_min: int | None = None,
    year_max: int | None = None,
    min_tmdb_score: float | None = None,
    min_tmdb_votes: int | None = None,
    with_genres: str | None = None,
    without_genres: str | None = None,
) -> dict[str, Any]:
    updated = dict(query)
    if year_min is not None:
        updated["year_min"] = int(year_min)
    if year_max is not None:
        updated["year_max"] = int(year_max)
    if min_tmdb_score is not None:
        updated["vote_average_gte"] = float(min_tmdb_score)
    if min_tmdb_votes is not None:
        updated["vote_count_gte"] = int(min_tmdb_votes)
    normalized_with_genres = normalize_optional_tmdb_genre_filter(with_genres)
    normalized_without_genres = normalize_optional_tmdb_genre_filter(without_genres)
    if normalized_with_genres is not None:
        updated["with_genres"] = normalized_with_genres
    if normalized_without_genres is not None:
        updated["without_genres"] = normalized_without_genres
    return updated


def build_tmdb_criteria_name(
    country: str,
    mode: str,
    year_min: int | None = None,
    min_tmdb_score: float | None = None,
) -> str:
    name = f"tmdb_{normalize_country_code(country)}_{mode}"
    if year_min is not None:
        name += f"_{int(year_min)}plus"
    if min_tmdb_score is not None:
        score = f"{float(min_tmdb_score):g}".replace(".", "_")
        name += f"_min{score}"
    return name
