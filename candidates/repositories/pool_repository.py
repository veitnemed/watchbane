"""JSON persistence for candidate_pool.json."""

from __future__ import annotations

import json
import os

from config import constant


def init_candidate_pool() -> None:
    """Создает JSON с пулом кандидатов, если его еще нет."""
    if os.path.exists(constant.CANDIDATE_POOL_JSON):
        return
    os.makedirs(os.path.dirname(constant.CANDIDATE_POOL_JSON), exist_ok=True)
    with open(constant.CANDIDATE_POOL_JSON, "w", encoding="utf-8") as file:
        json.dump({}, file, ensure_ascii=False, indent=4)


def load_candidate_pool() -> dict:
    """Загружает текущий пул кандидатов."""
    init_candidate_pool()
    with open(constant.CANDIDATE_POOL_JSON, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def save_candidate_pool(data: dict) -> None:
    """Сохраняет пул кандидатов."""
    from candidates.pool.normalization import normalize_storage_pool
    from candidates.pool.watched_cleanup import purge_watched_from_pool

    data = purge_watched_from_pool(normalize_storage_pool(data))
    with open(constant.CANDIDATE_POOL_JSON, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
