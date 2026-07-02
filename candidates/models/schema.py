"""Shared schema and completeness helpers for candidate-pool records."""

from __future__ import annotations

from typing import Any

from candidates.models import country_schema
from candidates.models import genre_schema
from candidates.models.keys import COMMON_POOL_CRITERIA_NAME


REQUIRED_FIELD_GROUPS = (
    ("tmdb_id", ("tmdb_id",)),
    ("title", ("title",)),
    ("year_or_first_air_date", ("year", "first_air_date")),
    ("tmdb_score", ("tmdb_score",)),
    ("tmdb_votes", ("tmdb_votes",)),
    ("genres", ("genres", "genre_keys", "genres_tmdb")),
    ("countries", ("countries", "country_codes", "origin_country")),
)
OPTIONAL_FIELD_GROUPS = (
    ("description_or_overview", ("description", "overview")),
    ("poster_path_or_poster_url", ("poster_path", "poster_url")),
    ("content_rating", ("content_rating",)),
    ("actors_top_or_crew_top", ("actors_top", "crew_top")),
    ("imdb_id", ("imdb_id",)),
)
EXTERNAL_RATING_FIELDS = frozenset({
    "kp_score",
    "kp_votes",
    "kp_rating",
    "kp_id",
    "kp_status",
    "kp_year",
    "imdb_score",
    "imdb_rating",
    "imdb_votes",
    "imdb_start_year",
    "imdb_end_year",
    "imdb_genres",
    "imdb_title_type",
    "imdb_is_adult",
    "imdb_found_in_sql",
})


def _copy_candidate(candidate: dict | None) -> dict:
    if isinstance(candidate, dict):
        return dict(candidate)
    return {}


def strip_external_rating_fields(candidate: dict) -> dict:
    """Returns a copy without KP/IMDb rating-enrichment fields."""
    updated = _copy_candidate(candidate)
    for field_name in EXTERNAL_RATING_FIELDS:
        updated.pop(field_name, None)
    return updated


def _normalize_list(value) -> list:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, (tuple, set)):
        return list(value)
    return []


def _has_value(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return value is not None and str(value).strip() != ""


def _has_any_field(candidate: dict, field_names: tuple[str, ...]) -> bool:
    return any(_has_value(candidate.get(field_name)) for field_name in field_names)


def coerce_candidate_number(value: Any) -> int | float | None:
    """Safely coerces candidate numeric fields for runtime filters without raising."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value

    text = str(value).strip()
    if text == "":
        return None

    lowered = text.casefold()
    if lowered in {"unknown", "n/a", "na", "-"}:
        return None
    if "/" in text:
        return None

    normalized = text
    if "," in normalized and "." not in normalized:
        left, right = normalized.split(",", 1)
        if right.isdigit() and len(right) <= 2:
            normalized = f"{left}.{right}"
        else:
            normalized = normalized.replace(",", "")

    try:
        if "." in normalized:
            return float(normalized)
        return int(normalized)
    except (TypeError, ValueError):
        return None


def compute_completeness(candidate: dict) -> dict:
    """Computes TMDb-only completeness for one candidate."""
    current = _copy_candidate(candidate)
    missing_fields = [
        group_name
        for group_name, field_names in REQUIRED_FIELD_GROUPS
        if _has_any_field(current, field_names) is False
    ]
    optional_missing_fields = [
        group_name
        for group_name, field_names in OPTIONAL_FIELD_GROUPS
        if _has_any_field(current, field_names) is False
    ]
    return {
        "is_complete": len(missing_fields) == 0,
        "missing_fields": missing_fields,
        "optional_missing_fields": optional_missing_fields,
    }


def ensure_candidate_defaults(candidate: dict) -> dict:
    """Backfills required schema fields while preserving unknown fields."""
    updated = strip_external_rating_fields(candidate)
    updated["title"] = updated.get("title") or updated.get("alternative_title") or ""
    updated["year"] = updated.get("year")
    updated["criteria_name"] = COMMON_POOL_CRITERIA_NAME
    updated["source"] = str(updated.get("source") or "").strip() or "tmdb"
    updated["source_provider"] = str(updated.get("source_provider") or "").strip() or "tmdb"
    updated["source_version"] = updated.get("source_version") or 2
    updated["signals"] = _normalize_list(updated.get("signals"))
    updated["genres"] = _normalize_list(updated.get("genres"))
    updated["countries"] = _normalize_list(updated.get("countries"))
    existing_country_codes = _normalize_list(updated.get("country_codes"))
    updated["country_codes"] = existing_country_codes or country_schema.build_country_codes(updated)
    updated["country_display"] = country_schema.build_country_display(updated["country_codes"])
    existing_genre_keys = _normalize_list(updated.get("genre_keys"))
    updated["genre_keys"] = existing_genre_keys or genre_schema.build_genre_keys(updated)
    updated["genres_display"] = genre_schema.build_genres_display(updated["genre_keys"])
    updated.setdefault("tmdb_score", None)
    updated.setdefault("tmdb_votes", None)
    updated.setdefault("tmdb_popularity", None)
    updated.setdefault("quality_score", None)
    updated.setdefault("hidden_gem_score", None)
    updated.setdefault("final_score", None)

    completeness = compute_completeness(updated)
    updated["is_complete"] = completeness["is_complete"]
    updated["missing_fields"] = completeness["missing_fields"]
    updated["optional_missing_fields"] = completeness["optional_missing_fields"]
    return updated


def is_candidate_complete(candidate: dict) -> bool:
    """Returns True when the candidate satisfies the TMDb-only required contract."""
    return compute_completeness(candidate)["is_complete"]


def normalize_candidate_record(candidate: dict) -> dict:
    """Returns a normalized candidate record without dropping unknown fields."""
    return ensure_candidate_defaults(candidate)


def resolve_canonical_year(candidate: dict) -> int | None:
    """Returns the canonical pool year from year or first_air_date only."""
    year_value = coerce_candidate_number(candidate.get("year"))
    if isinstance(year_value, int):
        return year_value
    if isinstance(year_value, float):
        return int(year_value)

    first_air_date = str(candidate.get("first_air_date") or "").strip()
    if len(first_air_date) >= 4 and first_air_date[:4].isdigit():
        return int(first_air_date[:4])
    return None


def normalize_candidate_for_storage(candidate: dict) -> dict:
    """Applies canonical year and schema defaults before pool write-path."""
    updated = strip_external_rating_fields(candidate)
    canonical_year = resolve_canonical_year(updated)
    if canonical_year is not None:
        updated["year"] = canonical_year
    return normalize_candidate_record(updated)
