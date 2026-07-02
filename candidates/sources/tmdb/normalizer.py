"""TMDb-only candidate normalizer for candidate pool records."""

from __future__ import annotations

from typing import Any

from apis import tmdb_api
from candidates.models import genre_schema
from candidates.models.schema import compute_completeness, strip_external_rating_fields


def _unique_non_empty(values) -> list:
    result = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if text == "" or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _names_from_items(items: list[dict[str, Any]] | None) -> list[str]:
    return tmdb_api.names_from_items(items)


def _country_names_from_items(items: list[dict[str, Any]] | None) -> list[str]:
    return tmdb_api.names_from_items(items)


def _genre_names(raw_details: dict[str, Any]) -> list[str]:
    return _names_from_items(raw_details.get("genres"))


def _genre_keys(genres: list[str]) -> list[str]:
    keys = []
    seen = set()
    for genre in genres:
        key = genre_schema.normalize_genre_to_key(genre)
        if key is None or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _country_codes(raw_details: dict[str, Any]) -> list[str]:
    origin_country = raw_details.get("origin_country") or []
    production_codes = tmdb_api.country_codes_from_items(raw_details.get("production_countries"))
    return _unique_non_empty(list(origin_country) + production_codes)


def _countries(raw_details: dict[str, Any]) -> list[str]:
    origin_country = raw_details.get("origin_country") or []
    production_countries = _country_names_from_items(raw_details.get("production_countries"))
    return _unique_non_empty(list(origin_country) + production_countries)


def _source_trace(source_trace) -> list:
    if source_trace is None:
        return []
    if isinstance(source_trace, list):
        return list(source_trace)
    return [source_trace]


def prepare_tmdb_candidate(
    raw_details: dict[str, Any],
    country=None,
    source_query=None,
    source_trace=None,
) -> dict:
    overview = tmdb_api.extract_best_overview(raw_details)
    poster_path = tmdb_api.extract_best_poster_path(raw_details)
    external_ids = tmdb_api.extract_external_ids(raw_details)
    credits = tmdb_api.extract_aggregate_credits_top(raw_details, limit=10)
    genres = _genre_names(raw_details)
    country_codes = _country_codes(raw_details)
    countries = _countries(raw_details)

    candidate = {
        "source": "tmdb",
        "source_provider": "tmdb",
        "source_version": 2,
        "tmdb_id": raw_details.get("id"),
        "title": raw_details.get("name"),
        "original_title": raw_details.get("original_name"),
        "year": tmdb_api.get_year(raw_details.get("first_air_date")),
        "first_air_date": raw_details.get("first_air_date"),
        "last_air_date": raw_details.get("last_air_date"),
        "description": overview,
        "overview": overview,
        "genres": genres,
        "genre_keys": _genre_keys(genres),
        "countries": countries,
        "country_codes": country_codes,
        "original_language": raw_details.get("original_language"),
        "networks": _names_from_items(raw_details.get("networks")),
        "production_companies": _names_from_items(raw_details.get("production_companies")),
        "tmdb_score": raw_details.get("vote_average"),
        "tmdb_votes": raw_details.get("vote_count"),
        "tmdb_popularity": raw_details.get("popularity"),
        "imdb_id": external_ids.get("imdb_id"),
        "poster_path": poster_path,
        "poster_url": tmdb_api.image_link(poster_path),
        "backdrop_path": raw_details.get("backdrop_path"),
        "backdrop_url": tmdb_api.image_link(raw_details.get("backdrop_path")),
        "content_rating": tmdb_api.get_content_rating(raw_details),
        "watch_providers": tmdb_api.get_watch_providers(raw_details),
        "actors_top": credits["actors_top"],
        "crew_top": credits["crew_top"],
        "keywords": tmdb_api.extract_keywords(raw_details),
        "source_query": dict(source_query or {}),
        "source_trace": _source_trace(source_trace),
    }
    if country is not None:
        candidate["target_country"] = str(country or "").strip().upper()

    candidate = strip_external_rating_fields(candidate)
    completeness = compute_completeness(candidate)
    candidate["is_complete"] = completeness["is_complete"]
    candidate["missing_fields"] = completeness["missing_fields"]
    candidate["optional_missing_fields"] = completeness["optional_missing_fields"]
    return candidate
