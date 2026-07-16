"""Deferred full-profile reset with backup and startup profile selection."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from typing import Any

from config.app_paths import get_app_paths
from storage import profiles


RESET_REQUEST_JSON = "profile_reset_request.json"
SELECTION_REQUIRED_JSON = "profile_selection_required.json"
DATABASE_NAMES = ("watchbane.sqlite3", "watchbane.sqlite", "watchbane.db")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _request_path() -> Path:
    return profiles.get_base_data_dir() / RESET_REQUEST_JSON


def _selection_path() -> Path:
    return profiles.get_base_data_dir() / SELECTION_REQUIRED_JSON


def request_full_profile_reset(profile: str | None = None) -> Path:
    """Persist a reset request that will be processed before SQLite startup."""
    target = profiles.get_active_profile() if profile is None else str(profile).strip().casefold()
    if profiles.profile_exists(target) is False:
        raise FileNotFoundError(f"Profile not found: {target}")
    path = _request_path()
    _write_json(
        path,
        {
            "profile": target,
            "requested_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return path


def profile_selection_required() -> bool:
    """Return whether startup must show the profile selector."""
    return _selection_path().is_file()


def clear_profile_selection_required() -> None:
    """Clear the one-shot selector marker after a successful choice."""
    _selection_path().unlink(missing_ok=True)


def _main_managed_paths() -> list[Path]:
    base = profiles.get_profile_data_dir(profiles.MAIN_PROFILE)
    installed = get_app_paths()
    if base.resolve() == installed.data_dir.resolve():
        ancillary = [
            installed.cache_dir,
            installed.posters_dir,
            installed.config_dir,
            installed.exports_dir,
            installed.logs_dir,
        ]
    else:
        ancillary = [
            base / "cache",
            base / "posters",
            base / "config",
            base / "exports",
            base / "logs",
        ]
    database_paths: list[Path] = []
    for name in DATABASE_NAMES:
        database = base / name
        database_paths.extend((database, Path(f"{database}-wal"), Path(f"{database}-shm")))
    return [
        *database_paths,
        base / ".env.local",
        base / "watched",
        base / "candidates",
        *ancillary,
    ]


def _backup_main_profile() -> Path:
    base = profiles.get_profile_data_dir(profiles.MAIN_PROFILE)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = base / "backups" / "profiles" / f"main_{stamp}"
    destination.mkdir(parents=True, exist_ok=False)
    for source in _main_managed_paths():
        if source.exists() is False:
            continue
        try:
            relative = source.relative_to(base)
            target = destination / "data" / relative
        except ValueError:
            target = destination / "runtime" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    return destination


def _reset_main_profile() -> Path:
    backup_path = _backup_main_profile()
    for path in _main_managed_paths():
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    return backup_path


def process_pending_profile_reset() -> dict[str, Any]:
    """Backup and clear one requested profile before runtime initialization."""
    request_path = _request_path()
    payload = _read_json(request_path)
    if not payload:
        return {"applied": False, "profile": None, "backup_path": None}
    target = str(payload.get("profile") or "").strip().casefold()
    if profiles.profile_exists(target) is False:
        raise FileNotFoundError(f"Profile not found: {target}")

    backup_path = (
        _reset_main_profile()
        if target == profiles.MAIN_PROFILE
        else profiles.reset_named_profile(target)
    )
    _write_json(
        _selection_path(),
        {
            "reset_profile": target,
            "backup_path": str(backup_path),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    request_path.unlink(missing_ok=True)
    return {
        "applied": True,
        "profile": target,
        "backup_path": str(backup_path),
    }
