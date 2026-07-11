"""Runtime data layout initialization."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import shutil

from config import constant
from config.app_paths import data_dir_override_active, get_app_paths, migrate_legacy_database
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
        constant.POSTERS_DIR,
        constant.EXPORTS_DIR,
        constant.LOGS_DIR,
        constant.CONFIG_DIR,
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
    """Initialize runtime directories and SQLite storage through one public entrypoint."""
    from app.core.storage import init_search_lists
    from candidates.repositories.criteria_repository import init_candidate_criteria
    from candidates.repositories.pool_repository import init_candidate_pool
    from storage.data import init_dataset, init_meta

    installed_paths = get_app_paths()
    if (
        data_dir_override_active() is False
        and Path(constant.APP_DATA_DIR).resolve() == installed_paths.data_dir.resolve()
    ):
        legacy_database_migration = migrate_legacy_database(paths=installed_paths)
    else:
        legacy_database_migration = {
            "status": "custom_runtime",
            "migrated": False,
            "db_path": str(Path(constant.APP_DATA_DIR) / "watchbane.sqlite3"),
            "backup_path": None,
        }

    directories = ensure_runtime_directories()
    init_meta()
    init_dataset()
    init_candidate_criteria()
    init_candidate_pool()
    init_search_lists()

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
        "backend": "sqlite",
        "directories": directories,
        "backup_created": backup_created,
        "sqlite_db_path": sqlite_db_path,
        "sqlite_schema_version": sqlite_schema_version,
        "sqlite_startup_migration": sqlite_startup_migration,
        "legacy_database_migration": legacy_database_migration,
    }


DEV_EMPTY_PROFILE_ENV = "WATCHBANE_DEV_EMPTY_PROFILE"
DEV_CLEAR_CANDIDATES_ENV = "WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START"


class DevStartupResetSafetyError(RuntimeError):
    """Raised when a destructive dev reset targets the main installed runtime."""


def _env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _active_data_root() -> Path:
    profiles.apply_active_profile_to_constants()
    return Path(constant.APP_DATA_DIR)


def _backup_active_data_root(reason: str) -> Path:
    data_root = _active_data_root()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_root = data_root / "backups" / "dev_startup" / f"{reason}_{stamp}"
    backup_root.parent.mkdir(parents=True, exist_ok=True)
    if data_root.exists():
        ignore = shutil.ignore_patterns("backups")
        shutil.copytree(data_root, backup_root, ignore=ignore)
    else:
        backup_root.mkdir(parents=True, exist_ok=True)
    return backup_root


def _remove_file(path: Path) -> None:
    if path.is_file():
        path.unlink()


def _empty_active_runtime_files() -> None:
    data_root = _active_data_root()
    for name in ("watchbane.sqlite3", "watchbane.sqlite", "watchbane.db"):
        db_path = data_root / name
        _remove_file(db_path)
        _remove_file(Path(str(db_path) + "-wal"))
        _remove_file(Path(str(db_path) + "-shm"))
    for relative in (
        "watched/titles.json",
        "watched/meta.json",
        "candidates/pool.json",
        "candidates/criteria.json",
        "candidates/watchlist.json",
        "candidates/hidden.json",
        "cache/posters/posters.json",
    ):
        _remove_file(data_root / relative)


def _clear_candidate_startup_tables() -> None:
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations

    conn = connect()
    try:
        apply_migrations(conn)
        with conn:
            conn.execute("DELETE FROM candidate_autofill_requests")
            conn.execute("DELETE FROM candidate_records")
            conn.execute("DELETE FROM candidate_criteria")
            conn.execute("DELETE FROM candidate_actions")
            conn.execute("DELETE FROM candidate_impressions")
            conn.execute("DELETE FROM onboarding_profiles")
    finally:
        conn.close()


def apply_dev_startup_reset_from_env() -> dict:
    """Apply explicit dev-only startup cleanup flags after creating a backup."""
    empty_profile = _env_enabled(DEV_EMPTY_PROFILE_ENV)
    clear_candidates = _env_enabled(DEV_CLEAR_CANDIDATES_ENV)
    if not empty_profile and not clear_candidates:
        return {"applied": False, "backup_path": None, "empty_profile": False, "clear_candidates": False}

    if data_dir_override_active() is False and profiles.get_active_profile() == profiles.MAIN_PROFILE:
        raise DevStartupResetSafetyError(
            f"{DEV_EMPTY_PROFILE_ENV} and {DEV_CLEAR_CANDIDATES_ENV} require WATCHBANE_DATA_DIR "
            "or an active sandbox profile."
        )

    reasons = []
    if empty_profile:
        reasons.append("empty_profile")
    if clear_candidates:
        reasons.append("clear_candidates")
    backup_path = _backup_active_data_root("_".join(reasons))

    if empty_profile:
        _empty_active_runtime_files()
    if clear_candidates and not empty_profile:
        _clear_candidate_startup_tables()

    return {
        "applied": True,
        "backup_path": str(backup_path),
        "empty_profile": empty_profile,
        "clear_candidates": clear_candidates,
    }
