"""File utilities plus SQLite-first backup and restore entrypoints."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from config import constant


def open_file(file_name: str) -> None:
    """Open a file with the Windows shell."""
    os.startfile(file_name)


def create_backup():
    """Create a SQLite runtime database backup."""
    from storage.sqlite.backup import backup_sqlite_database

    return backup_sqlite_database()


def get_latest_backups(limit: int = 10) -> list:
    """Return latest backup files known to the app."""
    backup_dir = Path(constant.BACKUP_DIR)
    if backup_dir.exists() is False:
        return []

    files = [
        path for path in backup_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".sqlite", ".sqlite3", ".db", ".json"}
    ]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files[:limit]


def get_backup_label(file_path: Path) -> str:
    """Build a compact backup label for menus."""
    size_kb = file_path.stat().st_size / 1024
    changed_at = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%d.%m.%Y %H:%M:%S")
    return f"{file_path.name} | {changed_at} | {size_kb:.1f} KB"


def restore_backup(file_path: Path) -> int:
    """Restore a SQLite backup, or explicitly import a legacy JSON dataset backup."""
    if Path(file_path).suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
        from storage.sqlite.backup import restore_sqlite_database

        return restore_sqlite_database(file_path)

    from storage.data import save_dataset

    with open(file_path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)

    if isinstance(data, dict) is False:
        raise ValueError("Backup must be a JSON mapping.")

    create_backup()
    save_dataset(data)
    return len(data)


def init_all_dates():
    """Initialize runtime data layout."""
    from storage.runtime import ensure_runtime_data_layout

    ensure_runtime_data_layout(create_initial_backup=True)
