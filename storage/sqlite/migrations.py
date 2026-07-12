"""Idempotent SQLite schema migration runner."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from threading import RLock

from storage.sqlite.connection import connect
from storage.sqlite.schema import apply_v1, apply_v2, apply_v3, apply_v4, apply_v5, apply_v6


MigrationFunc = Callable[[sqlite3.Connection], None]
_MIGRATION_LOCK = RLock()


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: MigrationFunc
    backup_before: bool = False


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "initial_schema_v1", apply_v1),
    Migration(2, "onboarding_candidate_autofill_v2", apply_v2),
    Migration(3, "candidate_fts_v3", apply_v3),
    Migration(4, "candidate_impressions_v4", apply_v4),
    Migration(5, "user_rating_scale_v5", apply_v5, backup_before=True),
    Migration(6, "recommendation_deck_state_v6", apply_v6),
)


class MigrationError(RuntimeError):
    """Raised when the SQLite migration history is inconsistent."""


def _validate_migration_plan(migrations: Iterable[Migration]) -> tuple[Migration, ...]:
    plan = tuple(migrations)
    seen: set[int] = set()
    duplicates: set[int] = set()
    for migration in plan:
        if migration.version in seen:
            duplicates.add(migration.version)
        seen.add(migration.version)
    if duplicates:
        duplicate_text = ", ".join(str(version) for version in sorted(duplicates))
        raise MigrationError(f"Duplicate SQLite migration version(s): {duplicate_text}")
    return plan


def ensure_schema_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          applied_at TEXT NOT NULL
        )
        """
    )


def get_current_schema_version(conn: sqlite3.Connection | None = None) -> int:
    """Return the highest applied schema migration version."""
    owned = conn is None
    active_conn = connect() if conn is None else conn
    try:
        ensure_schema_migrations_table(active_conn)
        row = active_conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
        ).fetchone()
        return int(row["version"] if row is not None else 0)
    finally:
        if owned:
            active_conn.close()


def _apply_migrations_unlocked(
    conn: sqlite3.Connection | None = None,
    *,
    migrations: Iterable[Migration] | None = None,
) -> int:
    """Apply pending migrations once and return the current schema version."""
    owned = conn is None
    active_conn = connect() if conn is None else conn
    migration_list = _validate_migration_plan(MIGRATIONS if migrations is None else migrations)
    try:
        ensure_schema_migrations_table(active_conn)
        applied = {
            int(row["version"]): str(row["name"])
            for row in active_conn.execute("SELECT version, name FROM schema_migrations")
        }
        for migration in sorted(migration_list, key=lambda item: item.version):
            applied_name = applied.get(migration.version)
            if applied_name is not None:
                if applied_name != migration.name:
                    raise MigrationError(
                        "SQLite migration history mismatch for version "
                        f"{migration.version}: stored {applied_name!r}, "
                        f"code defines {migration.name!r}"
                    )
                continue
            if migration.backup_before:
                database_row = active_conn.execute("PRAGMA database_list").fetchone()
                database_path = str(database_row["file"] or "") if database_row is not None else ""
                watched_count = int(
                    active_conn.execute("SELECT COUNT(*) AS count FROM watched_records").fetchone()["count"]
                )
                if database_path and watched_count > 0:
                    from pathlib import Path
                    from storage.sqlite.backup import backup_sqlite_database

                    active_conn.commit()
                    target = Path(database_path)
                    backup_sqlite_database(
                        db_path=target,
                        backup_dir=target.parent / "backups" / "migrations",
                    )
            with active_conn:
                migration.apply(active_conn)
                active_conn.execute(
                    """
                    INSERT INTO schema_migrations(version, name, applied_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        migration.version,
                        migration.name,
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    ),
                )
            applied[migration.version] = migration.name
        return get_current_schema_version(active_conn)
    finally:
        if owned:
            active_conn.close()


def apply_migrations(
    conn: sqlite3.Connection | None = None,
    *,
    migrations: Iterable[Migration] | None = None,
) -> int:
    """Apply pending migrations once, serialized across in-process workers."""
    with _MIGRATION_LOCK:
        return _apply_migrations_unlocked(conn, migrations=migrations)
