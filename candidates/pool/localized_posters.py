"""Lazy localized poster enrichment for candidate pool records."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from candidates.models.keys import pool_entry_key
from candidates.repositories import pool_repository
from dataset.language import normalize_data_language, tmdb_locale_for_data_language
from dataset.tmdb_localized import localized_blocks_from_tmdb_details

TMDB_DETAIL_FIELDS_CHECKED_AT = "tmdb_detail_fields_checked_at"
TV_METADATA_TRIGGER_FIELDS = (
    "number_of_seasons",
    "number_of_episodes",
    "status",
    "episode_run_time",
)
TV_DETAIL_FIELDS = (
    "first_air_date",
    "last_air_date",
    "last_episode_to_air",
    "status",
    "type",
    "in_production",
    "number_of_seasons",
    "number_of_episodes",
    "episode_run_time",
    "content_rating",
    "watch_providers",
    "networks",
    "production_companies",
    "actors_top",
    "crew_top",
    "keywords",
    "original_language",
    "imdb_id",
    "poster_path",
    "poster_url",
    "backdrop_path",
    "backdrop_url",
)
MOVIE_DETAIL_FIELDS = (
    "release_date",
    "status",
    "runtime",
    "imdb_runtime_minutes",
    "content_rating",
    "watch_providers",
    "production_companies",
    "actors_top",
    "crew_top",
    "keywords",
    "original_language",
    "imdb_id",
    "poster_path",
    "poster_url",
    "backdrop_path",
    "backdrop_url",
)


def _localized_poster_available(record: dict | None, data_language: str) -> bool:
    if isinstance(record, dict) is False:
        return False
    localized = record.get("localized") if isinstance(record.get("localized"), dict) else {}
    block = localized.get(normalize_data_language(data_language))
    if isinstance(block, dict) is False:
        return False
    return any(block.get(key) not in (None, "") for key in ("poster_url", "poster_path"))


def _has_value(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return value is not None and str(value).strip() != ""


def _candidate_tmdb_id(candidate: dict | None):
    if isinstance(candidate, dict) is False:
        return None
    if candidate.get("tmdb_id") not in (None, ""):
        return candidate.get("tmdb_id")
    source_query = candidate.get("source_query")
    if isinstance(source_query, dict):
        return source_query.get("tmdb_id")
    return None


def _candidate_media_type(candidate: dict | None) -> str:
    if isinstance(candidate, dict) is False:
        return "tv"

    source_query = candidate.get("source_query") if isinstance(candidate.get("source_query"), dict) else {}
    for field_name in ("media_type", "object_type", "type"):
        value = str(candidate.get(field_name) or "").strip().casefold()
        if value in {"movie", "film"}:
            return "movie"
        if value in {"tv", "series", "serial", "show"}:
            return "tv"

    query_media_type = str(source_query.get("media_type") or "").strip().casefold()
    if query_media_type in {"movie", "film"}:
        return "movie"
    if query_media_type in {"tv", "series", "serial", "show"}:
        return "tv"

    if candidate.get("release_date") not in (None, "") and candidate.get("first_air_date") in (None, ""):
        return "movie"
    return "tv"


def _candidate_needs_tv_metadata(candidate: dict | None) -> bool:
    if isinstance(candidate, dict) is False:
        return False
    if _candidate_media_type(candidate) != "tv":
        return False
    if candidate.get(TMDB_DETAIL_FIELDS_CHECKED_AT) not in (None, ""):
        return False
    return any(_has_value(candidate.get(field_name)) is False for field_name in TV_METADATA_TRIGGER_FIELDS)


def candidate_needs_tmdb_detail_enrichment(candidate: dict | None, data_language: str = "ru") -> bool:
    """Return True when a pool record should fetch TMDb details lazily."""
    if isinstance(candidate, dict) is False:
        return False
    return (
        _localized_poster_available(candidate, data_language) is False
        or _candidate_needs_tv_metadata(candidate)
    )


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


def _normalized_detail_candidate(details: dict, media_type: str, language: str) -> dict:
    from candidates.sources.tmdb.normalizer import prepare_tmdb_candidate, prepare_tmdb_movie_candidate

    source_query = {"language": normalize_data_language(language)}
    if media_type == "movie":
        return prepare_tmdb_movie_candidate(details, source_query=source_query)
    return prepare_tmdb_candidate(details, source_query=source_query)


def _merge_detail_fields(candidate: dict, details: dict, media_type: str, language: str) -> dict:
    if isinstance(details, dict) is False or not details:
        return candidate

    needs_tv_metadata = _candidate_needs_tv_metadata(candidate)
    detail_candidate = _normalized_detail_candidate(details, media_type, language)
    field_names = MOVIE_DETAIL_FIELDS if media_type == "movie" else TV_DETAIL_FIELDS
    updated = deepcopy(candidate)

    for field_name in field_names:
        value = detail_candidate.get(field_name)
        if _has_value(value) is False:
            continue
        if _has_value(updated.get(field_name)) is False:
            updated[field_name] = deepcopy(value)

    if media_type == "tv" and needs_tv_metadata:
        updated[TMDB_DETAIL_FIELDS_CHECKED_AT] = datetime.now().isoformat(timespec="seconds")
    return updated


def _fetch_details(tmdb_id: int, media_type: str, language: str, details_func=None) -> dict:
    from apis import tmdb_api

    tmdb_language = tmdb_locale_for_data_language(language)
    if details_func is not None:
        append_to_response = (
            tmdb_api.DEFAULT_MOVIE_DETAIL_APPENDS
            if media_type == "movie"
            else tmdb_api.DEFAULT_TV_DETAIL_APPENDS
        )
        return details_func(
            int(tmdb_id),
            language=tmdb_language,
            append_to_response=append_to_response,
        )

    if media_type == "movie":
        return tmdb_api.get_movie_details(
            int(tmdb_id),
            language=tmdb_language,
            append_to_response=tmdb_api.DEFAULT_MOVIE_DETAIL_APPENDS,
        )
    return tmdb_api.get_tv_details(
        int(tmdb_id),
        language=tmdb_language,
        append_to_response=tmdb_api.DEFAULT_TV_DETAIL_APPENDS,
    )


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
    """Fetch and persist localized poster and missing TMDb detail metadata on demand."""
    if isinstance(candidate, dict) is False:
        return candidate, False

    language = normalize_data_language(data_language)
    if candidate_needs_tmdb_detail_enrichment(candidate, language) is False:
        return candidate, False

    tmdb_id = _candidate_tmdb_id(candidate)
    if tmdb_id in (None, ""):
        return candidate, False

    media_type = _candidate_media_type(candidate)
    details = _fetch_details(int(tmdb_id), media_type, language, details_func)
    blocks = localized_blocks_from_tmdb_details(details, current_language=language)
    updated_candidate = deepcopy(candidate)
    if _localized_poster_available({"localized": blocks}, language):
        updated_candidate = _merge_localized_blocks(updated_candidate, blocks)
    updated_candidate = _merge_detail_fields(updated_candidate, details, media_type, language)

    changed = updated_candidate != candidate
    if changed is False:
        return candidate, False
    if persist is False:
        return updated_candidate, changed

    try:
        pool = pool_repository.load_candidate_pool()
        key = _find_pool_key(pool, candidate)
        if key is not None:
            pool_candidate = pool[key] if isinstance(pool[key], dict) else {}
            updated_pool_candidate = deepcopy(pool_candidate)
            if _localized_poster_available({"localized": blocks}, language):
                updated_pool_candidate = _merge_localized_blocks(updated_pool_candidate, blocks)
            updated_pool_candidate = _merge_detail_fields(updated_pool_candidate, details, media_type, language)
            if updated_pool_candidate != pool_candidate:
                pool[key] = updated_pool_candidate
                pool_repository.save_candidate_pool(pool)
                return pool[key], True
    except Exception:
        return updated_candidate, changed

    return updated_candidate, changed
