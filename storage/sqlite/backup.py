"""SQLite backup and restore helpers."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory

from config import constant
from storage.sqlite.connection import get_db_path
from storage.sqlite.startup import inspect_sqlite_startup


REQUIRED_BACKUP_TABLES = {
    "schema_migrations",
    "watched_records",
    "candidate_records",
    "candidate_criteria",
    "candidate_actions",
    "app_settings",
    "poster_cache_entries",
}


class RestoreTargetBusyError(sqlite3.OperationalError):
    """The current profile cannot safely be restored while in use."""


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

    if target.exists() and source.samefile(target):
        raise ValueError("SQLite backup destination must differ from its source")

    source_conn = sqlite3.connect(source)
    try:
        source_conn.execute("PRAGMA wal_checkpoint(FULL)")
        _publish_backup(source_conn, target)
    finally:
        source_conn.close()
    return target


def _publish_backup(source_conn: sqlite3.Connection, target: Path) -> None:
    # Only completed snapshots carry a backup suffix in the menu directory.
    # Same-directory staging also keeps the final rename on one filesystem.
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".watchbane-backup-", dir=target.parent) as staging:
        snapshot = Path(staging) / "snapshot.sqlite3"
        target_conn = sqlite3.connect(snapshot)
        try:
            source_conn.backup(target_conn)
            journal_mode = target_conn.execute("PRAGMA journal_mode=DELETE").fetchone()
            if journal_mode != ("delete",):
                raise sqlite3.DatabaseError("Could not stage SQLite backup as a single file")
            # Pre-migration snapshots may intentionally have an older schema.
            if target_conn.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise sqlite3.DatabaseError("SQLite backup failed quick_check")
        finally:
            target_conn.close()
        os.replace(snapshot, target)


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

    with TemporaryDirectory(prefix=".watchbane-restore-", dir=target.parent) as staging:
        snapshot = Path(staging) / "snapshot.sqlite3"
        source_conn = sqlite3.connect(source)
        try:
            _validate_backup_source(source_conn, source)
            staged_conn = sqlite3.connect(snapshot)
            try:
                source_conn.backup(staged_conn)
                if staged_conn.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
                    raise sqlite3.DatabaseError("Could not stage SQLite restore as a single file")
                _validate_backup_source(staged_conn, snapshot)
                row = staged_conn.execute("SELECT COUNT(*) FROM watched_records").fetchone()
                restored_count = int(row[0])
            finally:
                staged_conn.close()
        finally:
            source_conn.close()

        # Inspect exactly what will be restored using the next startup's rules.
        inspection = inspect_sqlite_startup(snapshot)
        if not inspection["ok"]:
            raise ValueError(f"Cannot restore SQLite backup: {inspection['reason']}")

        if target.is_file() and _restore_existing_database(snapshot, target):
            return restored_count

        # A new database or an explicitly selected corrupt runtime can use
        # offline replacement, but never delete or override active sidecars.
        for suffix in ("-wal", "-shm", "-journal"):
            if Path(str(target) + suffix).exists():
                raise RestoreTargetBusyError("Runtime has SQLite sidecars; close other profile sessions before restoring")
        if target.is_file():
            stamp = datetime.now().strftime("%d-%m-%Y %H-%M-%S-%f")
            preserved_dir = Path(constant.BACKUP_DIR) / "diagnostics" / f"pre_restore_{stamp}"
            preserved_dir.mkdir(parents=True, exist_ok=False)
            shutil.copy2(target, preserved_dir / target.name)
        os.replace(snapshot, target)
        return restored_count


def _restore_existing_database(snapshot: Path, target: Path) -> bool:
    """Restore in place while holding SQLite's exclusive profile lock.

    Return False only for proven corruption; contention/IO errors must never
    trigger file replacement around another connection's SQLite locks.
    """
    # mode=rw cannot silently recreate a target that disappeared.
    conn = sqlite3.connect(target.resolve().as_uri() + "?mode=rw", uri=True, timeout=0.25)
    try:
        try:
            conn.execute("PRAGMA locking_mode=EXCLUSIVE")
            conn.execute("BEGIN EXCLUSIVE")
            # Exercise the first page so NOTADB is distinguishable from busy.
            conn.execute("PRAGMA schema_version").fetchone()
            conn.commit()
        except sqlite3.DatabaseError as error:
            code = getattr(error, "sqlite_errorcode", 0) & 0xff
            if code in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
                return False
            if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise RestoreTargetBusyError("Runtime is locked; close other profile sessions before restoring") from error
            raise

        # Exclusive locking mode retains its lock after COMMIT. The online
        # backup API requires no open destination transaction and performs its
        # own atomic transaction without substituting the live database inode.
        stamp = datetime.now().strftime("%d-%m-%Y %H-%M-%S-%f")
        _publish_backup(conn, Path(constant.BACKUP_DIR) / f"{stamp}.sqlite3")
        staged_conn = sqlite3.connect(snapshot)
        try:
            staged_conn.backup(conn)
        finally:
            staged_conn.close()
        return True
    finally:
        conn.close()
