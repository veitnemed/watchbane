"""Explainable TMDb-only quality scoring for local series candidates."""

from __future__ import annotations

from candidates.models.schema import normalize_candidate_record
from candidates.sources.tmdb.scoring import (
    compute_metadata_completeness_score,
    compute_tmdb_final_score,
    compute_tmdb_hidden_gem_score,
    compute_tmdb_quality_score,
    compute_tmdb_vote_reliability,
)


def calculate_quality_score(candidate) -> float:
    """Calculates candidate quality from TMDb-only signals."""
    return compute_tmdb_quality_score(normalize_candidate_record(candidate))


def tmdb_vote_weight(tmdb_votes) -> float:
    """Compatibility wrapper for UI explanation text."""
    return compute_tmdb_vote_reliability({"tmdb_votes": tmdb_votes})


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Returns candidates sorted by TMDb-only quality, with score fields attached."""
    ranked = []
    for candidate in candidates:
        normalized = normalize_candidate_record(candidate)
        normalized["metadata_completeness_score"] = compute_metadata_completeness_score(normalized)
        normalized["quality_score"] = compute_tmdb_quality_score(normalized)
        normalized["hidden_gem_score"] = compute_tmdb_hidden_gem_score(normalized)
        normalized["final_score"] = compute_tmdb_final_score(normalized)
        ranked.append(normalized)
    ranked.sort(
        key=lambda item: (
            float(item.get("final_score") or 0),
            float(item.get("quality_score") or 0),
            float(item.get("tmdb_score") or 0),
            float(item.get("tmdb_votes") or 0),
            float(item.get("tmdb_popularity") or 0),
            float(item.get("metadata_completeness_score") or 0),
            str(item.get("title") or "").casefold(),
        ),
        reverse=True,
    )
    return ranked
