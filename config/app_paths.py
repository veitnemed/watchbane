"""Resolved runtime paths for installed and development builds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Mapping


APP_DIR_NAME = "Watchbane"
DATA_DIR_ENV = "WATCHBANE_DATA_DIR"
DB_FILENAME = "watchbane.sqlite3"


@dataclass(frozen=True, slots=True)
class AppPaths:
    root: Path
    data_dir: Path
    database_path: Path
    watched_dir: Path
    candidates_dir: Path
    cache_dir: Path
    posters_dir: Path
    logs_dir: Path
    backups_dir: Path
    config_dir: Path
    exports_dir: Path

    def directories(self) -> tuple[Path, ...]:
        return (
            self.root,
            self.data_dir,
            self.watched_dir,
            self.candidates_dir,
            self.cache_dir,
            self.posters_dir,
            self.logs_dir,
            self.backups_dir,
            self.config_dir,
            self.exports_dir,
        )


class LegacyDatabaseMigrationError(RuntimeError):
    """Raised when a legacy database cannot be copied without data loss."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def legacy_database_path() -> Path:
    return project_root() / "data" / DB_FILENAME


def data_dir_override_active(environ: Mapping[str, str] | None = None) -> bool:
    values = os.environ if environ is None else environ
    return bool(str(values.get(DATA_DIR_ENV) or "").strip())


def resolve_runtime_root(
    *,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: str | Path | None = None,
) -> Path:
    values = os.environ if environ is None else environ
    override = str(values.get(DATA_DIR_ENV) or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    platform_name = os.name if platform is None else platform
    home_dir = Path.home() if home is None else Path(home)
    if platform_name == "nt":
        local_app_data = str(values.get("LOCALAPPDATA") or "").strip()
        base = Path(local_app_data) if local_app_data else home_dir / "AppData" / "Local"
        return (base / APP_DIR_NAME).resolve()
    return (home_dir / ".local" / "share" / APP_DIR_NAME).resolve()


def build_app_paths(root: str | Path) -> AppPaths:
    runtime_root = Path(root).expanduser().resolve()
    data_dir = runtime_root / "data"
    return AppPaths(
        root=runtime_root,
        data_dir=data_dir,
        database_path=data_dir / DB_FILENAME,
        watched_dir=data_dir / "watched",
        candidates_dir=data_dir / "candidates",
        cache_dir=runtime_root / "cache",
        posters_dir=runtime_root / "posters",
        logs_dir=runtime_root / "logs",
        backups_dir=runtime_root / "backups",
        config_dir=runtime_root / "config",
        exports_dir=runtime_root / "exports",
    )


def get_app_paths(
    *,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
    home: str | Path | None = None,
) -> AppPaths:
    return build_app_paths(resolve_runtime_root(environ=environ, platform=platform, home=home))


def _migration_backup_path(paths: AppPaths, source: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return paths.backups_dir / "legacy_database" / stamp / source.name


def migrate_legacy_database(
    *,
    paths: AppPaths | None = None,
    source_path: str | Path | None = None,
) -> dict[str, object]:
    """Copy a repo-local legacy database into the user runtime without overwriting."""
    resolved_paths = get_app_paths() if paths is None else paths
    source = legacy_database_path() if source_path is None else Path(source_path)
    target = resolved_paths.database_path

    try:
        if source.resolve() == target.resolve():
            return {"status": "same_path", "migrated": False, "db_path": str(target), "backup_path": None}
    except OSError:
        pass
    if target.exists():
        return {"status": "target_exists", "migrated": False, "db_path": str(target), "backup_path": None}
    if source.is_file() is False:
        return {"status": "legacy_missing", "migrated": False, "db_path": str(target), "backup_path": None}

    backup_path = _migration_backup_path(resolved_paths, source)
    temp_target = target.with_suffix(target.suffix + ".migrating")
    try:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        source_connection = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
        backup_connection = sqlite3.connect(backup_path)
        try:
            source_connection.backup(backup_connection)
        finally:
            backup_connection.close()
            source_connection.close()
        if backup_path.stat().st_size <= 0:
            raise OSError("legacy database backup is empty")

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, temp_target)
        if temp_target.stat().st_size != backup_path.stat().st_size:
            raise OSError("legacy database copy size mismatch")
        os.replace(temp_target, target)
    except (OSError, sqlite3.Error) as error:
        try:
            temp_target.unlink(missing_ok=True)
        except OSError:
            pass
        raise LegacyDatabaseMigrationError(
            f"Could not migrate legacy database to {target}. Backup source remains at {source}."
        ) from error

    return {
        "status": "copied",
        "migrated": True,
        "db_path": str(target),
        "backup_path": str(backup_path),
    }
