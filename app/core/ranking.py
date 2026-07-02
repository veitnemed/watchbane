"""Explainable quality scoring for local series candidates."""

from __future__ import annotations

import math

from candidates.models.schema import coerce_candidate_number, normalize_candidate_record


def _number(value) -> float | None:
    coerced = coerce_candidate_number(value)
    if coerced is None:
        return None
    return float(coerced)


def imdb_vote_weight(imdb_votes) -> float:
    """Returns the IMDb signal weight based on vote reliability."""
    votes = _number(imdb_votes) or 0.0
    if votes < 300:
        return 0.05
    if votes < 1000:
        return 0.15
    if votes < 5000:
        return 0.25
    return 0.35


def tmdb_vote_weight(tmdb_votes) -> float:
    """Returns the TMDb signal weight based on vote reliability."""
    votes = _number(tmdb_votes) or 0.0
    if votes < 50:
        return 0.25
    if votes < 300:
        return 0.55
    if votes < 1000:
        return 0.8
    return 1.0


def _vote_bonus(votes, scale: float, cap: float) -> float:
    value = _number(votes) or 0.0
    if value <= 0:
        return 0.0
    return min(math.log10(value + 1.0) * scale, cap)


def calculate_quality_score(candidate) -> float:
    """Calculates a simple quality score without predicting a personal rating."""
    candidate = normalize_candidate_record(candidate)
    kp_score = _number(candidate.get("kp_score"))
    imdb_score = _number(candidate.get("imdb_score"))
    imdb_votes = _number(candidate.get("imdb_votes")) or 0.0
    tmdb_score = _number(candidate.get("tmdb_score"))
    tmdb_votes = _number(candidate.get("tmdb_votes")) or 0.0

    weighted_sum = 0.0
    weight_sum = 0.0

    if tmdb_score is not None:
        weight = tmdb_vote_weight(tmdb_votes)
        weighted_sum += tmdb_score * weight
        weight_sum += 1.0

    if kp_score is not None:
        weighted_sum += kp_score * 0.75
        weight_sum += 0.75

    if imdb_score is not None:
        weight = imdb_vote_weight(imdb_votes)
        weighted_sum += imdb_score * weight
        weight_sum += weight

    if weight_sum == 0:
        return 0.0

    score = weighted_sum / weight_sum
    score += _vote_bonus(tmdb_votes, scale=0.08, cap=0.5)
    score += _vote_bonus(candidate.get("kp_votes"), scale=0.15, cap=0.8)
    if imdb_votes >= 300:
        score += _vote_bonus(imdb_votes, scale=0.08, cap=0.4)
    return round(min(score, 10.0), 4)


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Returns candidates sorted by quality, with quality_score attached."""
    ranked = []
    for candidate in candidates:
        normalized = normalize_candidate_record(candidate)
        normalized["quality_score"] = calculate_quality_score(normalized)
        ranked.append(normalized)
    ranked.sort(
        key=lambda item: (
            float(item.get("quality_score") or 0),
            float(_number(item.get("tmdb_score")) or 0),
            float(_number(item.get("tmdb_votes")) or 0),
            float(_number(item.get("kp_score")) or 0),
            float(_number(item.get("kp_votes")) or 0),
            str(item.get("title") or "").casefold(),
        ),
        reverse=True,
    )
    return ranked
