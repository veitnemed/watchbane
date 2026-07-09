"""Weighted reranking of FTS text relevance and pool final_score."""

from __future__ import annotations

from candidates.models.keys import pool_entry_key
from candidates.models.schema import coerce_candidate_number

# Calibrated on 26-query bootstrap set (2026-07): grid 0.3–0.7, best precision@10 at 0.5/0.5.
W_BM25 = 0.5
W_FINAL = 0.5


def _candidate_key(candidate: dict) -> str:
    stored = candidate.get("pool_entry_key")
    if stored not in (None, ""):
        return str(stored)
    return pool_entry_key(candidate)


def _normalize_bm25_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    values = list(scores.values())
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return {key: 1.0 for key in scores}
    span = maximum - minimum
    return {key: (maximum - value) / span for key, value in scores.items()}


def combined_relevance_score(
    *,
    bm25_score: float | None,
    final_score: float | None,
    norm_bm25: float | None = None,
) -> float:
    """Higher is better. bm25 raw values are negative in SQLite FTS5."""
    final_value = float(final_score) if final_score is not None else 0.0
    if norm_bm25 is None:
        norm_bm25 = 0.0 if bm25_score is None else 0.5
    return (W_BM25 * float(norm_bm25)) + (W_FINAL * final_value)


def attach_text_relevance(
    candidates: list[dict],
    bm25_by_key: dict[str, float],
) -> list[dict]:
    """Attach ``text_relevance_score`` and ``combined_relevance_score`` fields."""
    normalized = _normalize_bm25_scores(bm25_by_key)
    enriched: list[dict] = []
    for candidate in candidates:
        payload = dict(candidate)
        key = _candidate_key(candidate)
        bm25_score = bm25_by_key.get(key)
        final_score = coerce_candidate_number(candidate.get("final_score"))
        norm_bm25 = normalized.get(key)
        payload["text_relevance_score"] = bm25_score
        payload["combined_relevance_score"] = combined_relevance_score(
            bm25_score=bm25_score,
            final_score=final_score,
            norm_bm25=norm_bm25,
        )
        enriched.append(payload)
    return enriched


def sort_by_relevance(candidates: list[dict]) -> list[dict]:
    """Sort by combined relevance, then final_score, then title."""
    def sort_key(candidate: dict) -> tuple:
        combined = coerce_candidate_number(candidate.get("combined_relevance_score")) or 0.0
        final_score = coerce_candidate_number(candidate.get("final_score")) or 0.0
        title = str(candidate.get("title") or candidate.get("name") or "").casefold()
        return (-combined, -final_score, title)

    return sorted(list(candidates), key=sort_key)
