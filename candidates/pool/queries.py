"""Read-only queries over saved candidate pool."""

from __future__ import annotations

from candidates.pool.normalization import normalize_storage_pool
from candidates.models.schema import (
    compute_completeness as schema_compute_completeness,
)
from candidates.scoring.sort_keys import candidate_sort_score


def _load_pool() -> dict:
    from candidates.repositories.pool_repository import load_candidate_pool

    return load_candidate_pool()


def get_candidates_by_criteria(criteria_name: str) -> list:
    """Возвращает кандидатов, собранных по выбранному набору критериев."""
    pool = normalize_storage_pool(_load_pool())
    candidates = [
        candidate
        for candidate in pool.values()
        if candidate.get("criteria_name") == criteria_name
    ]
    candidates.sort(
        key=candidate_sort_score,
        reverse=True,
    )
    return candidates


def get_all_candidates() -> list:
    """Возвращает всех кандидатов из общего пула."""
    pool = normalize_storage_pool(_load_pool())
    candidates = list(pool.values())
    candidates.sort(
        key=candidate_sort_score,
        reverse=True,
    )
    return candidates


def is_candidate_incomplete(candidate: dict) -> bool:
    """Проверяет, нужны ли кандидату повторные попытки добора KP."""
    return schema_compute_completeness(candidate)["is_complete"] is False


def get_incomplete_candidates(pool: dict, criteria_name: str | None = None) -> list:
    """Возвращает неполных кандидатов из общего пула, опционально по критерию."""
    return [
        candidate
        for candidate in pool.values()
        if isinstance(candidate, dict)
        and (criteria_name is None or candidate.get("criteria_name") == criteria_name)
        and is_candidate_incomplete(candidate)
    ]
