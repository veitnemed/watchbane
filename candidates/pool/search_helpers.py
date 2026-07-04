"""Runtime search filter defaults and legacy saved-pool filtering."""

from __future__ import annotations

from candidates.models import country_schema
from candidates.models import genre_schema
from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.repositories.criteria_repository import load_candidate_criteria
from candidates.models.schema import (
    coerce_candidate_number,
    is_candidate_complete as schema_is_candidate_complete,
    normalize_candidate_record,
)


def build_search_filter_defaults(criteria_name: str | None = None) -> dict:
    """Возвращает defaults runtime-фильтров поиска из единого candidate_criteria.json."""
    del criteria_name
    defaults = {
        "criteria_name": None,
        "source": None,
        "country": None,
        "year_min": None,
        "year_max": None,
        "include_genres": [],
        "exclude_genres": [],
        "min_tmdb_score": None,
        "min_tmdb_votes": None,
        "only_complete": True,
    }

    criteria = load_candidate_criteria().get(COMMON_POOL_CRITERIA_NAME) or {}
    if isinstance(criteria, dict) is False:
        return defaults

    country = str(criteria.get("country") or "").strip()
    defaults.update({
        "country": country or None,
        "year_min": criteria.get("min_year"),
        "year_max": criteria.get("max_year"),
        "include_genres": list(criteria.get("genres") or []),
        "exclude_genres": list(criteria.get("excluded_genres") or []),
        "min_tmdb_score": criteria.get("min_tmdb_score") or criteria.get("min_tmdb"),
        "min_tmdb_votes": criteria.get("min_tmdb_votes"),
    })
    return defaults


def collect_search_genre_options(candidates: list) -> list[str]:
    """Returns unique saved-pool genre labels for runtime search filters."""
    seen_keys = set()
    options = []
    for candidate in candidates:
        normalized = normalize_candidate_record(candidate)
        for genre_key in normalized.get("genre_keys") or []:
            if genre_key in seen_keys:
                continue
            label = genre_schema.GENRE_KEY_TO_DISPLAY.get(genre_key)
            if label is None:
                continue
            seen_keys.add(genre_key)
            options.append(label)
    return sorted(options, key=lambda value: str(value).casefold())


def collect_search_country_options(candidates: list) -> list[dict]:
    """Returns unique saved-pool country options for runtime search filters."""
    seen_codes: set[str] = set()
    options: list[dict] = []
    for candidate in candidates:
        normalized = normalize_candidate_record(candidate)
        for code in normalized.get("country_codes") or []:
            iso2 = str(code or "").strip().upper()
            if iso2 == "" or iso2 in seen_codes:
                continue
            seen_codes.add(iso2)
            options.append(
                {
                    "code": iso2,
                    "label": country_schema.build_country_display([iso2]) or iso2,
                }
            )
    return sorted(options, key=lambda row: str(row.get("label") or "").casefold())


def _candidate_list_values(candidate: dict, field_name: str) -> list[str]:
    values = []
    for item in candidate.get(field_name, []) or []:
        text = str(item or "").strip()
        if text != "":
            values.append(text)
    return values


def _matches_optional_country(candidate: dict, country_filter) -> bool:
    required_codes = country_schema.normalize_country_filter_list(country_filter)
    has_country_filter = False
    if isinstance(country_filter, str):
        has_country_filter = country_filter.strip() != ""
    elif isinstance(country_filter, (list, tuple, set)):
        has_country_filter = any(str(item or "").strip() for item in country_filter)
    elif country_filter not in (None, ""):
        has_country_filter = True
    if has_country_filter and len(required_codes) == 0:
        return False
    if len(required_codes) == 0:
        return True

    candidate_codes = _candidate_list_values(candidate, "country_codes")
    if len(candidate_codes) == 0:
        return False
    return country_schema.country_codes_match_any(candidate_codes, required_codes)


def _matches_optional_genres(candidate: dict, include_genres: list[str], exclude_genres: list[str]) -> bool:
    candidate_keys = _candidate_list_values(candidate, "genre_keys")
    exclude_keys = genre_schema.normalize_genre_filter_list(exclude_genres or [])
    if genre_schema.genre_keys_match_none(candidate_keys, exclude_keys) is False:
        return False
    include_raw = include_genres or []
    include_keys = genre_schema.normalize_genre_filter_list(include_raw)
    has_include_filter = any(str(genre or "").strip() for genre in include_raw)
    if has_include_filter and len(include_keys) == 0:
        return False
    if len(include_keys) == 0:
        return True
    return genre_schema.genre_keys_match_any(candidate_keys, include_keys)


def _matches_min_value(candidate: dict, field_name: str, min_value) -> bool:
    normalized_min = coerce_candidate_number(min_value)
    if normalized_min is None:
        return True
    current = coerce_candidate_number(candidate.get(field_name))
    if current is None:
        return False
    return current >= normalized_min


def _matches_max_value(candidate: dict, field_name: str, max_value) -> bool:
    normalized_max = coerce_candidate_number(max_value)
    if normalized_max is None:
        return True
    current = coerce_candidate_number(candidate.get(field_name))
    if current is None:
        return False
    return current <= normalized_max


def filter_saved_candidates_for_search(candidates: list, filters: dict) -> list:
    """Фильтрует уже сохранённых кандидатов из общего пула перед поиском."""
    source = filters.get("source")
    country = filters.get("country")
    year_min = filters.get("year_min")
    year_max = filters.get("year_max")
    include_genres = filters.get("include_genres") or []
    exclude_genres = filters.get("exclude_genres") or []
    min_tmdb_score = filters.get("min_tmdb_score") or filters.get("min_tmdb")
    min_tmdb_votes = filters.get("min_tmdb_votes")
    only_complete = filters.get("only_complete", True)

    filtered = []
    for candidate in candidates:
        candidate = normalize_candidate_record(candidate)
        if source and candidate.get("source") != source:
            continue
        if _matches_optional_country(candidate, country) is False:
            continue

        if _matches_min_value(candidate, "year", year_min) is False:
            continue
        if _matches_max_value(candidate, "year", year_max) is False:
            continue

        if _matches_optional_genres(candidate, include_genres, exclude_genres) is False:
            continue

        if _matches_min_value(candidate, "tmdb_score", min_tmdb_score) is False:
            continue
        if _matches_min_value(candidate, "tmdb_votes", min_tmdb_votes) is False:
            continue

        if only_complete and schema_is_candidate_complete(candidate) is False:
            continue

        filtered.append(candidate)

    return filtered
