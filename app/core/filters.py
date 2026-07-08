"""Runtime filters for saved series candidates."""

from __future__ import annotations

from candidates.models import country_schema, genre_schema
from candidates.models.keys import title_identity_key
from candidates.models.schema import coerce_candidate_number, normalize_candidate_record


def _criteria_value(criteria: dict, *names, default=None):
    for name in names:
        if name in criteria:
            return criteria.get(name)
    return default


def _number(value):
    return coerce_candidate_number(value)


def _matches_min(candidate: dict, field_name: str, value) -> bool:
    minimum = _number(value)
    if minimum is None:
        return True
    current = _number(candidate.get(field_name))
    return current is not None and current >= minimum


def _matches_max(candidate: dict, field_name: str, value) -> bool:
    maximum = _number(value)
    if maximum is None:
        return True
    current = _number(candidate.get(field_name))
    return current is not None and current <= maximum


def _list_values(candidate: dict, field_name: str) -> list[str]:
    values = []
    for item in candidate.get(field_name, []) or []:
        text = str(item or "").strip()
        if text:
            values.append(text)
    return values


def _matches_country(candidate: dict, country_filter) -> bool:
    required = country_schema.normalize_country_filter_list(country_filter)
    has_filter = False
    if isinstance(country_filter, str):
        has_filter = country_filter.strip() != ""
    elif isinstance(country_filter, (list, tuple, set)):
        has_filter = any(str(item or "").strip() for item in country_filter)
    elif country_filter not in (None, ""):
        has_filter = True
    if has_filter and len(required) == 0:
        return False
    if len(required) == 0:
        return True
    return country_schema.country_codes_match_any(_list_values(candidate, "country_codes"), required)


def _matches_genres(candidate: dict, include_genres, exclude_genres) -> bool:
    candidate_keys = _list_values(candidate, "genre_keys")
    excluded = genre_schema.normalize_genre_filter_list(exclude_genres or [])
    if genre_schema.genre_keys_match_none(candidate_keys, excluded) is False:
        return False

    include_raw = include_genres or []
    included = genre_schema.normalize_genre_filter_list(include_raw)
    has_include = any(str(item or "").strip() for item in include_raw)
    if has_include and len(included) == 0:
        return False
    return genre_schema.genre_keys_match_any(candidate_keys, included)


def _identity_set(values) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, dict):
        values = values.keys()
    result = set()
    for item in values:
        if isinstance(item, dict):
            identity = title_identity_key(item)
        else:
            identity = str(item or "").strip()
        if identity and identity != "|":
            result.add(identity)
    return result


def candidate_matches(candidate: dict, criteria: dict | None = None) -> bool:
    """Checks whether one candidate matches runtime search criteria."""
    criteria = criteria or {}
    candidate = normalize_candidate_record(candidate)

    if _criteria_value(criteria, "criteria_name") and candidate.get("criteria_name") != criteria.get("criteria_name"):
        return False
    if _criteria_value(criteria, "source") and candidate.get("source") != criteria.get("source"):
        return False
    if _matches_country(candidate, _criteria_value(criteria, "country", "countries")) is False:
        return False
    if _matches_min(candidate, "year", _criteria_value(criteria, "year_from", "min_year", "year_min")) is False:
        return False
    if _matches_max(candidate, "year", _criteria_value(criteria, "year_to", "max_year", "year_max")) is False:
        return False
    if _matches_genres(
        candidate,
        _criteria_value(criteria, "include_genres", "genres", default=[]),
        _criteria_value(criteria, "exclude_genres", "excluded_genres", default=[]),
    ) is False:
        return False
    if _matches_min(candidate, "tmdb_score", _criteria_value(criteria, "min_tmdb_score", "min_tmdb")) is False:
        return False
    if _matches_min(candidate, "tmdb_votes", _criteria_value(criteria, "min_tmdb_votes")) is False:
        return False

    if _criteria_value(criteria, "only_complete", default=False) and candidate.get("is_complete") is not True:
        return False

    identity = title_identity_key(candidate)
    if _criteria_value(criteria, "only_unwatched", default=True):
        if identity in _identity_set(_criteria_value(criteria, "watched_identities", "watched", default=set())):
            return False
    if _criteria_value(criteria, "hide_hidden", default=True):
        if identity in _identity_set(_criteria_value(criteria, "hidden_identities", "hidden", default=set())):
            return False

    return True


def filter_candidates(candidates: list[dict], criteria: dict | None = None) -> list[dict]:
    """Filters a candidate list without mutating the source records."""
    return [normalize_candidate_record(candidate) for candidate in candidates if candidate_matches(candidate, criteria)]
