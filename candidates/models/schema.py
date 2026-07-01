"""Shared schema and completeness helpers for candidate-pool records."""

from __future__ import annotations

from typing import Any

from candidates.models import country_schema
from candidates.models import genre_schema
from candidates.models.keys import COMMON_POOL_CRITERIA_NAME


COMPLETENESS_REQUIRED_FIELDS = (
    "kp_score",
    "kp_votes",
    "imdb_score",
    "imdb_votes",
)
_PRESERVED_KP_STATUSES = {
    "not_found",
    "error",
    "pending_limit",
    "cache_hit",
    "not_requested",
    "skipped_network_errors",
}


def _copy_candidate(candidate: dict | None) -> dict:
    if isinstance(candidate, dict):
        return dict(candidate)
    return {}


def _normalize_list(value) -> list:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, (tuple, set)):
        return list(value)
    return []


def _has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


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


def _effective_kp_status(candidate: dict) -> str:
    has_kp_data = _has_value(candidate.get("kp_score")) and _has_value(candidate.get("kp_votes"))
    if has_kp_data:
        return "done"

    current_status = str(candidate.get("kp_status") or "").strip()
    if current_status in _PRESERVED_KP_STATUSES:
        return current_status
    return "missing"


def compute_completeness(candidate: dict) -> dict:
    """Computes shared completeness and KP status for one candidate."""
    current = _copy_candidate(candidate)
    missing_fields = [
        field_name
        for field_name in COMPLETENESS_REQUIRED_FIELDS
        if _has_value(current.get(field_name)) is False
    ]
    kp_status = _effective_kp_status(current)
    return {
        "is_complete": len(missing_fields) == 0,
        "missing_fields": missing_fields,
        "kp_status": kp_status,
    }


def ensure_candidate_defaults(candidate: dict) -> dict:
    """Backfills required schema fields while preserving unknown fields."""
    updated = _copy_candidate(candidate)
    updated["title"] = updated.get("title") or updated.get("alternative_title") or ""
    updated["year"] = updated.get("year")
    updated["criteria_name"] = COMMON_POOL_CRITERIA_NAME
    updated["source"] = str(updated.get("source") or "").strip() or "legacy"
    updated["signals"] = _normalize_list(updated.get("signals"))
    updated["genres"] = _normalize_list(updated.get("genres"))
    updated["countries"] = _normalize_list(updated.get("countries"))
    updated["country_codes"] = country_schema.build_country_codes(updated)
    updated["country_display"] = country_schema.build_country_display(updated["country_codes"])
    updated["genre_keys"] = genre_schema.build_genre_keys(updated)
    updated["genres_display"] = genre_schema.build_genres_display(updated["genre_keys"])
    updated.setdefault("kp_score", None)
    updated.setdefault("kp_votes", None)
    updated.setdefault("imdb_score", None)
    updated.setdefault("imdb_votes", None)
    updated.setdefault("tmdb_score", None)
    updated.setdefault("tmdb_votes", None)

    completeness = compute_completeness(updated)
    updated["kp_status"] = completeness["kp_status"]
    updated["is_complete"] = completeness["is_complete"]
    return updated


def is_candidate_complete(candidate: dict) -> bool:
    """Returns True only when all search-required scores/votes are present."""
    return compute_completeness(candidate)["is_complete"]


def normalize_candidate_record(candidate: dict) -> dict:
    """Returns a normalized candidate record without dropping unknown fields."""
    return ensure_candidate_defaults(candidate)


def resolve_canonical_year(candidate: dict) -> int | None:
    """Returns the canonical pool year: imdb_start_year > year > kp_year."""
    for field_name in ("imdb_start_year", "year", "kp_year"):
        value = coerce_candidate_number(candidate.get(field_name))
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None


def normalize_candidate_for_storage(candidate: dict) -> dict:
    """Applies canonical year and schema defaults before pool write-path."""
    updated = _copy_candidate(candidate)
    canonical_year = resolve_canonical_year(updated)
    if canonical_year is not None:
        updated["year"] = canonical_year
    return normalize_candidate_record(updated)
