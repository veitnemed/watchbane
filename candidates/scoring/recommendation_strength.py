"""Qualitative recommendation-strength resolver for user-facing output."""

from __future__ import annotations

from typing import Any

from candidates.models.schema import coerce_candidate_number
from candidates.scoring.rating_confidence import (
    RATING_CONFIDENCE_KNOWN,
    candidate_rating_confidence,
)


RECOMMENDATION_STRONG_THRESHOLD = 0.72
RECOMMENDATION_PROMISING_THRESHOLD = 0.58
RECOMMENDATION_STRENGTH_KEYS = frozenset({
    "strong",
    "promising",
    "explore",
    "insufficient_data",
})


def normalize_recommendation_score(value: Any) -> float | None:
    score = coerce_candidate_number(value)
    if score is None or isinstance(score, bool):
        return None
    result = float(score)
    if 1 < result <= 10:
        result /= 10.0
    elif result > 10:
        result /= 100.0
    return max(0.0, min(1.0, result))


def resolve_recommendation_strength(
    final_score: Any,
    *,
    rating_confidence: str = RATING_CONFIDENCE_KNOWN,
) -> str:
    if str(rating_confidence or "") != RATING_CONFIDENCE_KNOWN:
        return "insufficient_data"
    score = normalize_recommendation_score(final_score)
    if score is None:
        return "insufficient_data"
    if score >= RECOMMENDATION_STRONG_THRESHOLD:
        return "strong"
    if score >= RECOMMENDATION_PROMISING_THRESHOLD:
        return "promising"
    return "explore"


def candidate_recommendation_strength(candidate: dict) -> str:
    return resolve_recommendation_strength(
        candidate.get("final_score"),
        rating_confidence=candidate_rating_confidence(candidate),
    )
