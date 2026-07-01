"""Sort and quality comparison keys for candidate pool records."""

from __future__ import annotations

from candidates.models.keys import title_identity_key
from candidates.schema import (
    coerce_candidate_number,
    is_candidate_complete as schema_is_candidate_complete,
)


def _to_optional_number(value) -> float | None:
    coerced = coerce_candidate_number(value)
    if coerced is None:
        return None
    return float(coerced)


def _sort_number(value) -> float:
    return _to_optional_number(value) or 0.0


def candidate_sort_score(candidate: dict) -> tuple:
    """Возвращает ключ качества кандидата для выбора лучшего дубля."""
    return (
        _sort_number(candidate.get("kp_score")),
        _sort_number(candidate.get("kp_votes")),
        _sort_number(candidate.get("imdb_score")),
        _sort_number(candidate.get("imdb_votes")),
    )


def _safe_rank_float(value) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _filled_score_votes_count(candidate: dict) -> int:
    count = 0
    for field_name in ("kp_score", "kp_votes", "imdb_score", "imdb_votes", "tmdb_score", "tmdb_votes"):
        if candidate.get(field_name) not in (None, ""):
            count += 1
    return count


def _candidate_quality_score(candidate: dict) -> float:
    return _safe_rank_float(candidate.get("quality_score"))


def _search_duplicate_tiebreak_key(candidate: dict, order_index: int) -> tuple:
    return (
        1 if schema_is_candidate_complete(candidate) else 0,
        1 if candidate.get("is_complete") is True else 0,
        _filled_score_votes_count(candidate),
        _safe_rank_float(candidate.get("quality_score")),
        _safe_rank_float(candidate.get("final_score")),
        _safe_rank_float(candidate.get("kp_score")),
        _safe_rank_float(candidate.get("imdb_score")),
        -order_index,
    )


def _is_better_search_duplicate(
    challenger: dict,
    incumbent: dict,
    challenger_index: int,
    incumbent_index: int,
) -> bool:
    return _search_duplicate_tiebreak_key(challenger, challenger_index) > _search_duplicate_tiebreak_key(
        incumbent,
        incumbent_index,
    )


def dedupe_ranked_candidates_by_title_identity(ranked_candidates: list) -> list:
    """Keeps one best candidate per normalized title/year for search display."""
    best_by_identity: dict[str, dict] = {}
    best_index_by_identity: dict[str, int] = {}
    order: list[str] = []

    for index, candidate in enumerate(ranked_candidates):
        identity = title_identity_key(candidate)
        if identity == "|":
            identity = f"__row_{index}"

        current = best_by_identity.get(identity)
        if current is None:
            best_by_identity[identity] = candidate
            best_index_by_identity[identity] = index
            order.append(identity)
            continue

        if _is_better_search_duplicate(
            candidate,
            current,
            index,
            best_index_by_identity[identity],
        ):
            best_by_identity[identity] = candidate
            best_index_by_identity[identity] = index

    deduped = [best_by_identity[identity] for identity in order]
    deduped.sort(
        key=_candidate_quality_score,
        reverse=True,
    )
    return deduped
