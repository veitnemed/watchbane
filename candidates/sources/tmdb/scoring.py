"""TMDb-only scoring helpers for candidate pool records."""

from __future__ import annotations

import math
from typing import Any

from candidates.models.schema import coerce_candidate_number


def _number(value) -> float | None:
    coerced = coerce_candidate_number(value)
    if coerced is None:
        return None
    return float(coerced)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def _candidate_country_codes(candidate: dict[str, Any]) -> set[str]:
    values = []
    for field_name in ("country_codes", "origin_country", "tmdb_origin_countries", "tmdb_country_codes"):
        raw = candidate.get(field_name) or []
        if isinstance(raw, str):
            values.extend(part.strip() for part in raw.split(","))
        elif isinstance(raw, (list, tuple, set)):
            values.extend(str(item or "").strip() for item in raw)
    return {value.upper() for value in values if value}


def _is_ru_candidate(candidate: dict[str, Any]) -> bool:
    target_country = str(candidate.get("target_country") or candidate.get("country") or "").strip().upper()
    if target_country in {"RU", "RUSSIA", "РОССИЯ"}:
        return True
    return "RU" in _candidate_country_codes(candidate)


def _rating_value(candidate: dict[str, Any]) -> float:
    rating = _number(candidate.get("tmdb_score"))
    if rating is None:
        rating = _number(candidate.get("tmdb_rating"))
    return _clamp(float(rating or 0.0), 0.0, 10.0)


def _vote_count(candidate: dict[str, Any]) -> int:
    votes = _number(candidate.get("tmdb_votes"))
    return max(0, int(votes or 0))


def _popularity_component(candidate: dict[str, Any]) -> float:
    popularity = _number(candidate.get("tmdb_popularity")) or 0.0
    if popularity <= 0:
        return 0.0
    target = 40.0 if _is_ru_candidate(candidate) else 100.0
    return round(_clamp(math.log10(popularity + 1.0) / math.log10(target + 1.0)), 4)


def _country_score(candidate: dict[str, Any]) -> float:
    existing = _number(candidate.get("country_score"))
    if existing is not None:
        return _clamp(existing)
    if _is_ru_candidate(candidate):
        return 1.0
    return 0.6 if len(_candidate_country_codes(candidate)) > 0 else 0.0


def compute_tmdb_bayesian_rating(candidate: dict[str, Any], country_prior: float = 6.8) -> float:
    rating = _rating_value(candidate)
    votes = _vote_count(candidate)
    m = 40.0 if _is_ru_candidate(candidate) else 200.0
    score = ((votes / (votes + m)) * rating) + ((m / (votes + m)) * float(country_prior))
    return round(_clamp(score / 10.0), 4)


def compute_tmdb_vote_reliability(candidate: dict[str, Any]) -> float:
    votes = _vote_count(candidate)
    if votes <= 0:
        return 0.0
    target = 300 if _is_ru_candidate(candidate) else 2000
    return round(_clamp(math.log10(votes + 1.0) / math.log10(target + 1.0)), 4)


def _vote_evidence_multiplier(candidate: dict[str, Any]) -> float:
    """Softly discounts weak TMDb vote evidence without hiding RU low-vote shows."""
    reliability = compute_tmdb_vote_reliability(candidate)
    return 0.50 + 0.50 * reliability


def _low_vote_final_cap(candidate: dict[str, Any]) -> float | None:
    votes = _vote_count(candidate)
    if votes <= 0:
        return 0.36
    if votes == 1:
        return 0.40
    if votes <= 4:
        return 0.44
    if votes <= 9:
        return 0.52
    return None


def compute_metadata_completeness_score(candidate: dict[str, Any]) -> float:
    checks = (
        ("description", "overview"),
        ("poster_path", "poster_url"),
        ("genres", "genre_keys", "genres_tmdb"),
        ("countries", "country_codes", "origin_country"),
        ("content_rating",),
        ("actors_top", "crew_top"),
        ("keywords",),
        ("networks", "production_companies"),
        ("first_air_date", "year"),
        ("imdb_id",),
    )
    filled = 0
    for fields in checks:
        if any(candidate.get(field) not in (None, "", []) for field in fields):
            filled += 1
    return round(filled / len(checks), 4)


def compute_tmdb_quality_score(candidate: dict[str, Any]) -> float:
    bayesian = compute_tmdb_bayesian_rating(candidate)
    reliability = compute_tmdb_vote_reliability(candidate)
    country_score = _country_score(candidate)
    popularity = _popularity_component(candidate)
    metadata = compute_metadata_completeness_score(candidate)
    score = (
        0.48 * bayesian
        + 0.18 * reliability
        + 0.14 * country_score
        + 0.10 * popularity
        + 0.10 * metadata
    )
    score *= _vote_evidence_multiplier(candidate)
    return round(_clamp(score), 4)


def compute_tmdb_hidden_gem_score(candidate: dict[str, Any]) -> float:
    bayesian = compute_tmdb_bayesian_rating(candidate)
    reliability = compute_tmdb_vote_reliability(candidate)
    popularity = _popularity_component(candidate)
    metadata = compute_metadata_completeness_score(candidate)
    rating = _rating_value(candidate)
    if rating < 7.0:
        return 0.0
    low_popularity_bonus = 1.0 - min(popularity, 1.0)
    vote_window = 1.0 - abs(reliability - 0.55)
    score = 0.42 * bayesian + 0.24 * _clamp(vote_window) + 0.22 * low_popularity_bonus + 0.12 * metadata
    score *= _vote_evidence_multiplier(candidate)
    return round(_clamp(score), 4)


def compute_tmdb_final_score(candidate: dict[str, Any], mode: str = "quality") -> float:
    quality_score = _number(candidate.get("quality_score"))
    if quality_score is None:
        quality_score = compute_tmdb_quality_score(candidate)
    hidden_gem_score = _number(candidate.get("hidden_gem_score"))
    if hidden_gem_score is None:
        hidden_gem_score = compute_tmdb_hidden_gem_score(candidate)
    country_score = _country_score(candidate)
    if mode == "hidden_gems":
        score = 0.58 * quality_score + 0.27 * hidden_gem_score + 0.15 * country_score
    else:
        score = 0.82 * quality_score + 0.18 * country_score
    cap = _low_vote_final_cap(candidate)
    if cap is not None:
        score = min(score, cap)
    return round(_clamp(score), 4)
