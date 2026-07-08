"""SQLite backup and restore helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3

from config import constant
from storage.sqlite.connection import get_db_path


REQUIRED_BACKUP_TABLES = {
    "schema_migrations",
    "watched_records",
    "candidate_records",
    "candidate_criteria",
    "candidate_actions",
    "app_settings",
    "poster_cache_entries",
}


def checkpoint_wal(db_path: str | Path | None = None) -> None:
    source = Path(db_path) if db_path is not None else get_db_path()
    if source.is_file() is False:
        return
    conn = sqlite3.connect(source)
    try:
        conn.execute("PRAGMA wal_checkpoint(FULL)")
    finally:
        conn.close()


def backup_sqlite_database(
    *,
    db_path: str | Path | None = None,
    backup_dir: str | Path | None = None,
    timestamp: str | None = None,
) -> Path:
    """Create a consistent SQLite database backup and return its path."""
    source = Path(db_path) if db_path is not None else get_db_path()
    if source.is_file() is False:
        raise FileNotFoundError(f"SQLite database does not exist: {source}")

    target_dir = Path(backup_dir) if backup_dir is not None else Path(constant.BACKUP_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp or datetime.now().strftime("%d-%m-%Y %H-%M-%S-%f")
    target = target_dir / f"{stamp}.sqlite3"

    source_conn = sqlite3.connect(source)
    try:
        source_conn.execute("PRAGMA wal_checkpoint(FULL)")
        target_conn = sqlite3.connect(target)
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
    finally:
        source_conn.close()
    return target


def _validate_backup_source(conn: sqlite3.Connection, source: Path) -> None:
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing = sorted(REQUIRED_BACKUP_TABLES - tables)
    if missing:
        raise ValueError(
            f"SQLite backup is missing required table(s): {', '.join(missing)} ({source})"
        )

    quick_check = [row[0] for row in conn.execute("PRAGMA quick_check")]
    if quick_check != ["ok"]:
        raise ValueError(f"SQLite backup failed quick_check: {source}")

    foreign_key_rows = list(conn.execute("PRAGMA foreign_key_check"))
    if foreign_key_rows:
        raise ValueError(f"SQLite backup failed foreign_key_check: {source}")


def restore_sqlite_database(
    backup_path: str | Path,
    *,
    db_path: str | Path | None = None,
) -> int:
    """Restore a SQLite backup and return watched record count."""
    source = Path(backup_path)
    if source.is_file() is False:
        raise FileNotFoundError(f"SQLite backup does not exist: {source}")

    target = Path(db_path) if db_path is not None else get_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    source_conn = sqlite3.connect(source)
    try:
        _validate_backup_source(source_conn, source)

        target_conn = sqlite3.connect(target)
        try:
            source_conn.backup(target_conn)
            row = target_conn.execute("SELECT COUNT(*) FROM watched_records").fetchone()
            return int(row[0])
        finally:
            target_conn.close()
    finally:
        source_conn.close()
