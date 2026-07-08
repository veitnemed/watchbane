"""JSON persistence for candidate_pool.json."""

from __future__ import annotations

import json
import os

from config import constant
from candidates.repositories.json_io import dump_json_atomic
from storage.backend import is_sqlite_backend


def init_candidate_pool() -> None:
    """Создает JSON с пулом кандидатов, если его еще нет."""
    if is_sqlite_backend():
        from storage.sqlite.migrations import apply_migrations

        apply_migrations()
        return

    if os.path.exists(constant.CANDIDATE_POOL_JSON):
        return
    dump_json_atomic(constant.CANDIDATE_POOL_JSON, {})


def load_candidate_pool() -> dict:
    """Загружает текущий пул кандидатов."""
    if is_sqlite_backend():
        from storage.sqlite.candidate_repository import load_candidate_pool_dict

        return load_candidate_pool_dict()

    if not os.path.exists(constant.CANDIDATE_POOL_JSON):
        return {}
    with open(constant.CANDIDATE_POOL_JSON, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def save_candidate_pool(data: dict) -> None:
    """Сохраняет пул кандидатов."""
    if is_sqlite_backend():
        from storage.sqlite.candidate_repository import save_candidate_pool_dict

        save_candidate_pool_dict(data)
        return

    from candidates.pool.normalization import normalize_storage_pool
    from candidates.pool.watched_cleanup import purge_watched_from_pool

    data = purge_watched_from_pool(normalize_storage_pool(data))
    dump_json_atomic(constant.CANDIDATE_POOL_JSON, data)
