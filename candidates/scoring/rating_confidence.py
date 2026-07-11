"""Shared semantics for candidates whose external rating is not established yet."""

from __future__ import annotations

from datetime import date
from typing import Any

from candidates.models.schema import coerce_candidate_number, resolve_canonical_year


RATING_CONFIDENCE_KNOWN = "known"
RATING_CONFIDENCE_UNKNOWN = "unknown"
RATING_CONFIDENCE_UNAVAILABLE = "unavailable"


def candidate_vote_count(candidate: dict[str, Any]) -> int | None:
    for field_name in ("tmdb_votes", "vote_count"):
        if field_name not in candidate:
            continue
        value = coerce_candidate_number(candidate.get(field_name))
        if value is None:
            continue
        return max(0, int(value))
    return None


def candidate_rating_confidence(candidate: dict[str, Any]) -> str:
    votes = candidate_vote_count(candidate)
    if votes is None:
        return RATING_CONFIDENCE_UNAVAILABLE
    if votes == 0:
        return RATING_CONFIDENCE_UNKNOWN
    return RATING_CONFIDENCE_KNOWN


def has_unknown_rating(candidate: dict[str, Any]) -> bool:
    return candidate_rating_confidence(candidate) == RATING_CONFIDENCE_UNKNOWN


def candidate_rating_value(candidate: dict[str, Any]) -> float | None:
    if has_unknown_rating(candidate):
        return None
    for field_name in ("tmdb_score", "tmdb_rating", "vote_average"):
        value = coerce_candidate_number(candidate.get(field_name))
        if value is not None:
            return max(0.0, min(10.0, float(value)))
    return None


def is_viable_unrated_candidate(candidate: dict[str, Any], *, current_year: int | None = None) -> bool:
    """Reject stale, sparse unrated records while preserving complete new releases."""
    if not has_unknown_rating(candidate):
        return True

    year = resolve_canonical_year(candidate)
    current = int(current_year or date.today().year)
    overview = bool(str(candidate.get("overview") or candidate.get("description") or "").strip())
    poster = candidate.get("poster_path") not in (None, "") or candidate.get("poster_url") not in (None, "")
    genres = bool(candidate.get("genres") or candidate.get("genre_keys") or candidate.get("genres_tmdb") or candidate.get("genre_ids"))
    dated = year is not None
    metadata_signals = sum((overview, poster, genres, dated))

    if year is not None and year < current - 2 and not overview:
        return False
    if year is not None and year >= current - 2:
        return metadata_signals >= 4
    return overview and metadata_signals >= 3
