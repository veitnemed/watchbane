"""JSON persistence for candidate_criteria.json."""

from __future__ import annotations

import json
import os
from datetime import datetime

from config import constant
from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.repositories import pool_repository


def init_candidate_criteria() -> None:
    """Создает JSON с критериями подбора, если его еще нет."""
    if os.path.exists(constant.CRITERIA_POOL_JSON):
        return
    os.makedirs(os.path.dirname(constant.CRITERIA_POOL_JSON), exist_ok=True)
    with open(constant.CRITERIA_POOL_JSON, "w", encoding="utf-8") as file:
        json.dump({}, file, ensure_ascii=False, indent=4)


def load_candidate_criteria() -> dict:
    """Загружает сохраненные критерии подбора."""
    init_candidate_criteria()
    with open(constant.CRITERIA_POOL_JSON, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def save_candidate_criteria(data: dict) -> None:
    """Сохраняет критерии подбора."""
    with open(constant.CRITERIA_POOL_JSON, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def save_named_criteria(criteria_name: str, criteria: dict) -> tuple[str, dict]:
    """Сохраняет именованный набор критериев и возвращает его."""
    all_criteria = load_candidate_criteria()
    all_criteria[criteria_name] = criteria
    save_candidate_criteria(all_criteria)
    return criteria_name, criteria


def patch_criteria_filters(
    criteria_name: str,
    current: dict,
    *,
    min_tmdb_score,
    genres: list,
    excluded_genres: list,
) -> dict:
    """Обновляет у набора критериев только блок фильтрации."""
    all_criteria = load_candidate_criteria()

    updated = dict(current)
    updated["min_tmdb_score"] = min_tmdb_score
    updated["genres"] = genres
    updated["excluded_genres"] = excluded_genres
    updated["updated_at"] = datetime.now().isoformat(timespec="seconds")

    all_criteria[criteria_name] = updated
    save_candidate_criteria(all_criteria)
    return updated


def build_criteria_label(criteria_name: str, criteria: dict) -> str:
    """Формирует короткую подпись сохраненного набора критериев."""
    parts = [criteria_name]
    if criteria.get("count"):
        parts.append(f"count={criteria['count']}")
    if criteria.get("min_tmdb_score") is not None:
        parts.append(f"TMDb>={criteria['min_tmdb_score']}")
    if criteria.get("min_year") is not None:
        parts.append(f"year>={criteria['min_year']}")
    if criteria.get("country"):
        parts.append(criteria["country"])
    if criteria.get("genres"):
        parts.append(f"жанры={len(criteria['genres'])}")
    if criteria.get("excluded_genres"):
        parts.append(f"искл={len(criteria['excluded_genres'])}")
    return " | ".join(parts)


def ensure_common_pool_criteria() -> tuple[str, dict]:
    """Returns the single shared criteria entry, creating it when missing."""
    all_criteria = load_candidate_criteria()
    existing = all_criteria.get(COMMON_POOL_CRITERIA_NAME)
    if isinstance(existing, dict):
        return COMMON_POOL_CRITERIA_NAME, existing

    criteria = {
        "country": None,
        "count": 50,
        "min_tmdb_score": None,
        "min_year": None,
        "max_year": None,
        "genres": [],
        "excluded_genres": [],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    return save_named_criteria(COMMON_POOL_CRITERIA_NAME, criteria)


def clear_common_pool() -> dict:
    """Removes all candidates from the shared pool without touching watched dataset."""
    pool = pool_repository.load_candidate_pool()
    cleared = len(pool)
    pool_repository.save_candidate_pool({})
    return {"ok": True, "cleared": cleared}


def delete_criteria_and_candidates(criteria_name: str) -> dict:
    """Удаляет набор критериев и все связанные с ним объекты из общего пула."""
    from candidates.pool.normalization import normalize_storage_pool

    all_criteria = load_candidate_criteria()
    if criteria_name not in all_criteria:
        return {
            "deleted_criteria": False,
            "deleted_candidates": 0,
        }

    all_criteria.pop(criteria_name, None)
    save_candidate_criteria(all_criteria)

    pool = normalize_storage_pool(pool_repository.load_candidate_pool())
    filtered_pool = {}
    deleted_candidates = 0
    for key, candidate in pool.items():
        if candidate.get("criteria_name") == criteria_name:
            deleted_candidates += 1
            continue
        filtered_pool[key] = candidate
    pool_repository.save_candidate_pool(filtered_pool)

    return {
        "deleted_criteria": True,
        "deleted_candidates": deleted_candidates,
    }
