"""Normalize and migrate saved candidate pool storage."""

from __future__ import annotations

from candidates.models.keys import pool_entry_key
from candidates.pool.dedupe import deduplicate_pool
from candidates.repositories import pool_repository
from candidates.schema import normalize_candidate_for_storage
from candidates.scoring.sort_keys import candidate_sort_score


def migrate_pool_keys(pool: dict) -> dict:
    """Переводит legacy-ключи пула на criteria-aware формат."""
    migrated = {}
    for candidate in pool.values():
        if isinstance(candidate, dict) is False:
            continue
        candidate = normalize_candidate_for_storage(candidate)
        key = pool_entry_key(candidate)
        current_best = migrated.get(key)
        if current_best is None or candidate_sort_score(candidate) > candidate_sort_score(current_best):
            migrated[key] = candidate
    return migrated


def normalize_storage_pool(pool: dict) -> dict:
    """Приводит пул к каноническому виду без удаления просмотренных (read-path)."""
    if isinstance(pool, dict) is False:
        return {}
    return deduplicate_pool(migrate_pool_keys(pool))


def normalize_pool(pool: dict) -> dict:
    """Legacy wrapper: только storage-normalize, без purge watched."""
    return normalize_storage_pool(pool)


def normalize_or_migrate_candidate_pool_file() -> dict:
    """Явно мигрирует и нормализует candidate_pool.json."""
    from candidates.pool.watched_cleanup import purge_watched_from_pool

    original = pool_repository.load_candidate_pool()
    normalized = purge_watched_from_pool(normalize_storage_pool(original))
    changed = normalized != original
    if changed:
        pool_repository.save_candidate_pool(normalized)
    return {
        "changed": changed,
        "before": len(original) if isinstance(original, dict) else 0,
        "after": len(normalized),
    }
