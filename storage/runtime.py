"""Runtime data layout initialization."""

from __future__ import annotations

import os

from config import constant
from storage.backend import get_storage_backend, is_sqlite_backend
from storage import profiles


RUNTIME_DIRECTORIES = None


def _runtime_directories() -> tuple[str, ...]:
    if RUNTIME_DIRECTORIES is not None:
        return tuple(RUNTIME_DIRECTORIES)
    return (
        constant.APP_DATA_DIR,
        constant.WATCHED_DIR,
        constant.CANDIDATES_DIR,
        constant.CACHE_DIR,
        constant.EXPORTS_DIR,
        constant.LOGS_DIR,
        constant.BACKUP_DIR,
    )


def ensure_runtime_directories() -> list[str]:
    """Create standard runtime directories and return their paths."""
    profiles.apply_active_profile_to_constants()
    created_or_existing = []
    for directory in _runtime_directories():
        os.makedirs(directory, exist_ok=True)
        created_or_existing.append(directory)
    return created_or_existing


def ensure_runtime_data_layout(*, create_initial_backup: bool = False) -> dict:
    """Initialize runtime JSON files and directories through one public entrypoint."""
    from app.core.storage import init_search_lists
    from candidates.repositories.criteria_repository import init_candidate_criteria
    from candidates.repositories.pool_repository import init_candidate_pool
    from storage.data import init_dataset, init_meta

    directories = ensure_runtime_directories()
    init_meta()
    init_dataset()
    init_candidate_criteria()
    init_candidate_pool()
    init_search_lists()

    sqlite_db_path = None
    sqlite_schema_version = None
    sqlite_startup_migration = None
    if is_sqlite_backend():
        from storage.sqlite.startup import ensure_sqlite_startup_migration

        sqlite_startup_migration = ensure_sqlite_startup_migration(
            base_dir=constant.APP_DATA_DIR,
        )
        sqlite_db_path = sqlite_startup_migration["db_path"]
        sqlite_schema_version = sqlite_startup_migration["schema_version"]

    backup_created = False
    if create_initial_backup:
        from storage.files import create_backup

        create_backup()
        backup_created = True

    return {
        "ok": True,
        "backend": get_storage_backend(),
        "directories": directories,
        "backup_created": backup_created,
        "sqlite_db_path": sqlite_db_path,
        "sqlite_schema_version": sqlite_schema_version,
        "sqlite_startup_migration": sqlite_startup_migration,
    }
