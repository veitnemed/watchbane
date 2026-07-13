"""Application boundary for pre-UI SQLite recovery."""

from __future__ import annotations

from storage.sqlite.backup import restore_sqlite_database
from storage.sqlite.startup import StartupDatabaseError, startup_database_error_message


def is_startup_database_error(error: BaseException) -> bool:
    return isinstance(error, StartupDatabaseError)


def format_startup_database_error(error: BaseException) -> str:
    if not isinstance(error, StartupDatabaseError):
        raise TypeError("Expected StartupDatabaseError")
    return startup_database_error_message(error)


def restore_selected_startup_backup(backup_path: str, error: BaseException) -> int:
    if not isinstance(error, StartupDatabaseError):
        raise TypeError("Expected StartupDatabaseError")
    return restore_sqlite_database(backup_path, db_path=error.db_path)
