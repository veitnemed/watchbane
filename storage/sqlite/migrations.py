"""Idempotent SQLite schema migration runner."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3

from storage.sqlite.connection import connect


MigrationFunc = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: MigrationFunc


MIGRATIONS: tuple[Migration, ...] = ()


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


def apply_migrations(
    conn: sqlite3.Connection | None = None,
    *,
    migrations: Iterable[Migration] | None = None,
) -> int:
    """Apply pending migrations once and return the current schema version."""
    owned = conn is None
    active_conn = connect() if conn is None else conn
    migration_list = tuple(MIGRATIONS if migrations is None else migrations)
    try:
        ensure_schema_migrations_table(active_conn)
        applied = {
            int(row["version"])
            for row in active_conn.execute("SELECT version FROM schema_migrations")
        }
        for migration in sorted(migration_list, key=lambda item: item.version):
            if migration.version in applied:
                continue
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
            applied.add(migration.version)
        return get_current_schema_version(active_conn)
    finally:
        if owned:
            active_conn.close()

