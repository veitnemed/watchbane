"""SQLite startup initialization."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sqlite3

from config import constant
from storage.sqlite.connection import connect, get_db_path
from storage.sqlite.migrations import MIGRATIONS, apply_migrations
from storage.sqlite.schema import apply_v3, apply_v6


IMPORT_MARKER_KEY = "legacy_json_import_completed"
SUPPORTED_SCHEMA_VERSION = max(migration.version for migration in MIGRATIONS)

_CORE_TABLES_BY_VERSION = {
    1: {
        "watched_records",
        "candidate_records",
        "candidate_criteria",
        "candidate_actions",
        "app_settings",
        "poster_cache_entries",
    },
    2: {"onboarding_profiles", "candidate_autofill_requests"},
    4: {"candidate_impressions"},
}
_REPAIRABLE_DERIVED_TABLES = {
    3: ("candidate_fts", apply_v3),
    6: ("recommendation_deck_state", apply_v6),
}


class StartupDatabaseError(RuntimeError):
    """Raised before the main UI when the runtime database is unsafe to mutate."""

    def __init__(self, reason: str, *, db_path: Path, preserved_path: Path | None = None):
        super().__init__(reason)
        self.reason = reason
        self.db_path = db_path
        self.preserved_path = preserved_path


def _readonly_connection(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def inspect_sqlite_startup(db_path: str | Path | None = None) -> dict:
    """Inspect an existing runtime without creating, journaling, or repairing it."""
    target = Path(db_path) if db_path is not None else get_db_path()
    if not target.is_file():
        return {"ok": True, "status": "new", "db_path": str(target), "repair_tables": []}

    try:
        conn = _readonly_connection(target)
        try:
            quick_check = [str(row[0]) for row in conn.execute("PRAGMA quick_check")]
            if quick_check != ["ok"]:
                return {
                    "ok": False,
                    "status": "corrupt",
                    "db_path": str(target),
                    "reason": "SQLite integrity check failed.",
                    "repair_tables": [],
                }
            tables = {
                str(row[0])
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")
            }
            if "schema_migrations" in tables:
                rows = list(conn.execute("SELECT version, name FROM schema_migrations ORDER BY version"))
            else:
                rows = []
            applied = {int(row["version"]): str(row["name"]) for row in rows}
            current = max(applied, default=0)
            if current > SUPPORTED_SCHEMA_VERSION:
                return {
                    "ok": False,
                    "status": "newer_schema",
                    "db_path": str(target),
                    "reason": (
                        f"Database schema {current} is newer than supported schema "
                        f"{SUPPORTED_SCHEMA_VERSION}."
                    ),
                    "repair_tables": [],
                }
            expected_names = {migration.version: migration.name for migration in MIGRATIONS}
            mismatches = [
                version
                for version, name in applied.items()
                if expected_names.get(version) != name
            ]
            if mismatches:
                return {
                    "ok": False,
                    "status": "migration_history_mismatch",
                    "db_path": str(target),
                    "reason": "SQLite migration history is inconsistent.",
                    "repair_tables": [],
                }

            missing_core: set[str] = set()
            for version, required in _CORE_TABLES_BY_VERSION.items():
                if version in applied:
                    missing_core.update(required - tables)
            if missing_core:
                return {
                    "ok": False,
                    "status": "partial_schema",
                    "db_path": str(target),
                    "reason": "SQLite schema is incomplete: " + ", ".join(sorted(missing_core)),
                    "repair_tables": [],
                }

            repair_tables = [
                table
                for version, (table, _apply) in _REPAIRABLE_DERIVED_TABLES.items()
                if version in applied and table not in tables
            ]
            return {
                "ok": True,
                "status": "ready" if not repair_tables else "repairable_derived_schema",
                "db_path": str(target),
                "schema_version": current,
                "repair_tables": repair_tables,
            }
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return {
            "ok": False,
            "status": "not_a_database",
            "db_path": str(target),
            "reason": "The runtime file is not a readable SQLite database.",
            "repair_tables": [],
        }


def _preserve_failed_database(source: Path) -> Path | None:
    """Copy the untouched failed runtime for diagnostics; never replace it."""
    try:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target_dir = Path(constant.BACKUP_DIR) / "diagnostics" / stamp
        target_dir.mkdir(parents=True, exist_ok=False)
        target = target_dir / source.name
        shutil.copy2(source, target)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(source) + suffix)
            if sidecar.is_file():
                shutil.copy2(sidecar, target_dir / sidecar.name)
        return target
    except OSError:
        return None


def startup_database_error_message(error: StartupDatabaseError) -> str:
    preserved = (
        f"\n\nДиагностическая копия: {error.preserved_path}"
        if error.preserved_path is not None
        else "\n\nНе удалось создать диагностическую копию. Исходный файл не изменён."
    )
    return (
        "Не удалось безопасно открыть локальную базу Watchbane.\n"
        "Основное окно не запущено, исходные данные не изменены.\n\n"
        f"Причина: {error.reason}\n"
        "Восстановление из резервной копии выполняется только вручную в инструментах восстановления."
        f"{preserved}"
    )


def _repair_derived_tables(conn: sqlite3.Connection, table_names: list[str]) -> None:
    by_table = {table: apply for table, apply in _REPAIRABLE_DERIVED_TABLES.values()}
    if not table_names:
        return
    conn.execute("SAVEPOINT watchbane_derived_schema_repair")
    try:
        for table in table_names:
            by_table[table](conn)
        conn.execute("RELEASE SAVEPOINT watchbane_derived_schema_repair")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT watchbane_derived_schema_repair")
        conn.execute("RELEASE SAVEPOINT watchbane_derived_schema_repair")
        raise


def is_sqlite_runtime_empty(db_path: str | Path | None = None) -> bool:
    conn = connect(db_path)
    try:
        apply_migrations(conn)
        checks = (
            "SELECT COUNT(*) AS count FROM watched_records",
            "SELECT COUNT(*) AS count FROM candidate_records",
            "SELECT COUNT(*) AS count FROM candidate_criteria",
            "SELECT COUNT(*) AS count FROM candidate_actions",
            "SELECT COUNT(*) AS count FROM candidate_impressions",
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
    """Create or migrate the SQLite runtime schema."""
    target_db = Path(db_path) if db_path is not None else get_db_path()
    inspection = inspect_sqlite_startup(target_db)
    if inspection["ok"] is False:
        preserved_path = _preserve_failed_database(target_db)
        raise StartupDatabaseError(
            str(inspection["reason"]),
            db_path=target_db,
            preserved_path=preserved_path,
        )
    conn = connect(target_db)
    try:
        _repair_derived_tables(conn, list(inspection["repair_tables"]))
        schema_version = apply_migrations(conn)
    finally:
        conn.close()

    return {
        "ok": True,
        "db_path": str(target_db),
        "schema_version": schema_version,
        "preflight_status": inspection["status"],
        "repaired_tables": list(inspection["repair_tables"]),
        "legacy_imported": False,
        "legacy_import_report": None,
    }

