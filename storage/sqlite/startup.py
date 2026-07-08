"""SQLite startup initialization and legacy import flow."""

from __future__ import annotations

import json
from pathlib import Path

from storage.sqlite.connection import connect, get_db_path
from storage.sqlite.import_legacy import import_legacy_json_to_sqlite, legacy_paths
from storage.sqlite.migrations import apply_migrations, get_current_schema_version
from storage.sqlite.settings_repository import set_setting


IMPORT_MARKER_KEY = "legacy_json_import_completed"


def _load_mapping(path: Path) -> dict:
    if path.is_file() is False:
        return {}
    try:
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def legacy_json_has_user_data(base_dir: str | Path) -> bool:
    paths = legacy_paths(base_dir)
    for path in (
        paths.titles,
        paths.meta,
        paths.candidate_pool,
        paths.candidate_criteria,
        paths.watchlist,
        paths.hidden,
        paths.settings,
        paths.poster_cache,
    ):
        if len(_load_mapping(path)) > 0:
            return True
    return False


def is_sqlite_runtime_empty(db_path: str | Path | None = None) -> bool:
    conn = connect(db_path)
    try:
        apply_migrations(conn)
        checks = (
            "SELECT COUNT(*) AS count FROM watched_records",
            "SELECT COUNT(*) AS count FROM candidate_records",
            "SELECT COUNT(*) AS count FROM candidate_criteria",
            "SELECT COUNT(*) AS count FROM candidate_actions",
            "SELECT COUNT(*) AS count FROM app_settings",
            "SELECT COUNT(*) AS count FROM poster_cache_entries",
        )
        return all(int(conn.execute(sql).fetchone()["count"]) == 0 for sql in checks)
    finally:
        conn.close()


def ensure_sqlite_startup_migration(
    *,
    base_dir: str | Path = "data",
    db_path: str | Path | None = None,
) -> dict:
    """Create SQLite schema and import legacy JSON once when appropriate."""
    target_db = Path(db_path) if db_path is not None else get_db_path()
    conn = connect(target_db)
    try:
        schema_version = apply_migrations(conn)
    finally:
        conn.close()

    imported = False
    import_report = None
    if is_sqlite_runtime_empty(target_db) and legacy_json_has_user_data(base_dir):
        import_report = import_legacy_json_to_sqlite(
            base_dir=base_dir,
            db_path=target_db,
            dry_run=False,
            create_backup=True,
        )
        set_setting(
            IMPORT_MARKER_KEY,
            {
                "completed": True,
                "source": "legacy_json",
                "counts": import_report.get("counts", {}),
            },
            path=target_db,
        )
        imported = True
        schema_version = get_current_schema_version()

    return {
        "ok": True,
        "db_path": str(target_db),
        "schema_version": schema_version,
        "legacy_imported": imported,
        "legacy_import_report": import_report,
    }

