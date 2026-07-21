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
INSTANCE_LOCK_FILE = "watchbane.instance.lock"
DATABASE_NAMES = ("watchbane.sqlite3", "watchbane.sqlite", "watchbane.db")
RESET_MODE_PROFILE_BACKUP = "profile_backup"
RESET_MODE_FACTORY_KEEP_TOKEN = "factory_keep_token"
TMDB_CREDENTIAL_KEYS = frozenset(
    {
        "TMDB_ACCESS_TOKEN",
        "TMDB_TOKEN",
        "TMDB_API_KEY",
    }
)


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
            "mode": RESET_MODE_PROFILE_BACKUP,
            "requested_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return path


def request_factory_reset_keep_token() -> Path:
    """Persist a no-backup factory reset while retaining current TMDb credentials."""
    target = profiles.get_active_profile()
    if profiles.profile_exists(target) is False:
        raise FileNotFoundError(f"Profile not found: {target}")
    path = _request_path()
    _write_json(
        path,
        {
            "profile": target,
            "mode": RESET_MODE_FACTORY_KEEP_TOKEN,
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


def _tmdb_credential_lines(*data_dirs: Path) -> list[str]:
    credentials: dict[str, str] = {}
    for data_dir in data_dirs:
        for name in (".env.local", "tmdb.env", ".env"):
            path = data_dir / name
            if path.is_file() is False:
                continue
            try:
                lines = path.read_text(encoding="utf-8-sig").splitlines()
            except OSError:
                continue
            for raw_line in lines:
                stripped = raw_line.strip()
                if stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key in TMDB_CREDENTIAL_KEYS and value:
                    credentials[key] = value
    return [f"{key}={value}" for key, value in credentials.items()]


def _write_tmdb_credentials(data_dir: Path, lines: list[str]) -> None:
    if not lines:
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / ".env.local"
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _factory_reset_paths() -> list[Path]:
    base = profiles.get_base_data_dir()
    installed = get_app_paths()
    if base.resolve() != installed.data_dir.resolve():
        return [base]
    legacy_root_paths: list[Path] = []
    for name in DATABASE_NAMES:
        database = installed.root / name
        legacy_root_paths.extend((database, Path(f"{database}-wal"), Path(f"{database}-shm")))
    legacy_root_paths.extend(
        (
            installed.root / "watched",
            installed.root / "candidates",
            installed.root / ".env.local",
            installed.root / "tmdb.env",
            installed.root / ".env",
        )
    )
    return [
        installed.data_dir,
        *legacy_root_paths,
        installed.cache_dir,
        installed.posters_dir,
        installed.config_dir,
        installed.exports_dir,
        installed.logs_dir,
        installed.backups_dir,
    ]


def _assert_factory_path_safe(path: Path) -> None:
    resolved = path.resolve()
    if resolved == resolved.parent or resolved == Path.home().resolve():
        raise RuntimeError(f"Unsafe factory reset path: {resolved}")
    base = profiles.get_base_data_dir().resolve()
    installed = get_app_paths()
    if base == installed.data_dir.resolve():
        allowed_root = installed.root.resolve()
        if resolved != allowed_root and resolved.is_relative_to(allowed_root) is False:
            raise RuntimeError(f"Factory reset path escapes runtime root: {resolved}")
    elif resolved != base:
        raise RuntimeError(f"Factory reset path escapes profile registry: {resolved}")


def _delete_factory_path(path: Path, *, preserve_instance_lock: bool) -> None:
    """Delete one reset target while keeping the current process lock releasable."""
    if path.is_dir() is False:
        if path.exists():
            path.unlink()
        return
    if preserve_instance_lock is False or (path / INSTANCE_LOCK_FILE).is_file() is False:
        shutil.rmtree(path)
        return
    for child in path.iterdir():
        if child.name == INSTANCE_LOCK_FILE:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _reset_factory_keep_token() -> None:
    base = profiles.get_base_data_dir()
    active_data_dir = profiles.get_active_data_dir()
    installed = get_app_paths()
    # Older builds kept their runtime and credentials directly under the app
    # root. Preserve a credential from there only when the active profile has
    # none, then delete those stale artifacts with the rest of the reset.
    credential_dirs = [installed.root, active_data_dir]
    credentials = _tmdb_credential_lines(*credential_dirs)
    paths = _factory_reset_paths()
    for path in paths:
        _assert_factory_path_safe(path)
    for path in paths:
        _delete_factory_path(path, preserve_instance_lock=path.resolve() == base.resolve())
    _write_tmdb_credentials(base, credentials)
    profiles.apply_profile_to_constants(profiles.MAIN_PROFILE)


def process_pending_profile_reset() -> dict[str, Any]:
    """Backup and clear one requested profile before runtime initialization."""
    request_path = _request_path()
    payload = _read_json(request_path)
    if not payload:
        return {"applied": False, "profile": None, "backup_path": None}
    target = str(payload.get("profile") or "").strip().casefold()
    if profiles.profile_exists(target) is False:
        raise FileNotFoundError(f"Profile not found: {target}")
    mode = str(payload.get("mode") or RESET_MODE_PROFILE_BACKUP).strip().casefold()
    if mode == RESET_MODE_FACTORY_KEEP_TOKEN:
        _reset_factory_keep_token()
        return {
            "applied": True,
            "profile": profiles.MAIN_PROFILE,
            "backup_path": None,
            "mode": RESET_MODE_FACTORY_KEEP_TOKEN,
        }
    if mode != RESET_MODE_PROFILE_BACKUP:
        raise ValueError(f"Unsupported profile reset mode: {mode}")

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
        "mode": RESET_MODE_PROFILE_BACKUP,
    }
