"""Safe local data profile management for main and sandbox datasets."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from config import constant
from config.app_paths import get_app_paths

MAIN_PROFILE = "main"
SANDBOX_PROFILE = "sandbox"
SANDBOX_KIND = "sandbox"
ACTIVE_PROFILE_JSON = "active_profile.json"
PROFILE_META_JSON = "profile.json"
_BASE_DATA_DIR_OVERRIDE: Path | None = None


class ProfileError(RuntimeError):
    """Base profile management error."""


class ProfileSafetyError(ProfileError):
    """Raised when an unsafe profile operation is rejected."""


def _clean_profile_name(name: str) -> str:
    text = str(name or "").strip().casefold()
    if text == "":
        raise ValueError("Profile name is empty.")
    if any(char in text for char in ('/', '\\', ':', '*', '?', '"', '<', '>', '|')):
        raise ValueError(f"Unsafe profile name: {name!r}")
    if text in {".", ".."}:
        raise ValueError(f"Unsafe profile name: {name!r}")
    return text


def _base_data_dir() -> Path:
    if _BASE_DATA_DIR_OVERRIDE is not None:
        return _BASE_DATA_DIR_OVERRIDE
    return Path(constant.APP_DATA_DIR)


def set_base_data_dir(path: str | Path | None) -> None:
    """Set the profile root independently from the currently active data dir."""
    global _BASE_DATA_DIR_OVERRIDE
    _BASE_DATA_DIR_OVERRIDE = None if path is None else Path(path)


def _active_profile_path() -> Path:
    return _base_data_dir() / ACTIVE_PROFILE_JSON


def _profiles_root() -> Path:
    return _base_data_dir() / "profiles"


def get_profile_data_dir(name: str) -> Path:
    """Return the data root for a profile without creating it."""
    profile = _clean_profile_name(name)
    if profile == MAIN_PROFILE:
        return _base_data_dir()
    return _profiles_root() / profile


def get_active_data_dir() -> Path:
    """Return the currently active data root."""
    return get_profile_data_dir(get_active_profile())


def _profile_meta_path(name: str) -> Path:
    return get_profile_data_dir(name) / PROFILE_META_JSON


def _read_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _profile_exists(name: str) -> bool:
    profile = _clean_profile_name(name)
    if profile == MAIN_PROFILE:
        return True
    data_dir = get_profile_data_dir(profile)
    return data_dir.is_dir() and _profile_meta_path(profile).is_file()


def _profile_kind(name: str) -> str:
    profile = _clean_profile_name(name)
    if profile == MAIN_PROFILE:
        return MAIN_PROFILE
    meta = _read_json(_profile_meta_path(profile))
    return str(meta.get("kind") or "").strip().casefold()


def get_active_profile() -> str:
    """Return the persisted active profile, falling back safely to main."""
    payload = _read_json(_active_profile_path())
    try:
        profile = _clean_profile_name(str(payload.get("active_profile") or MAIN_PROFILE))
    except ValueError:
        return MAIN_PROFILE
    if _profile_exists(profile):
        return profile
    return MAIN_PROFILE


def list_profiles() -> list[str]:
    """Return known data profile names."""
    names = {MAIN_PROFILE}
    root = _profiles_root()
    if root.is_dir():
        for child in root.iterdir():
            if child.is_dir() and (child / PROFILE_META_JSON).is_file():
                names.add(child.name)
    return [MAIN_PROFILE] + sorted(name for name in names if name != MAIN_PROFILE)


def _empty_profile_paths(data_dir: Path) -> dict[str, Path]:
    return {
        "titles": data_dir / "watched" / "titles.json",
        "meta": data_dir / "watched" / "meta.json",
        "candidate_pool": data_dir / "candidates" / "pool.json",
        "candidate_criteria": data_dir / "candidates" / "criteria.json",
        "watchlist": data_dir / "candidates" / "watchlist.json",
        "hidden": data_dir / "candidates" / "hidden.json",
        "poster_cache": data_dir / "cache" / "posters" / "posters.json",
    }


def _ensure_profile_layout(data_dir: Path) -> None:
    for directory in (
        data_dir,
        data_dir / "watched",
        data_dir / "candidates",
        data_dir / "cache",
        data_dir / "cache" / "posters",
        data_dir / "cache" / "posters" / "images",
        data_dir / "exports",
        data_dir / "logs",
        data_dir / "backups",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def create_sandbox_profile(name: str = SANDBOX_PROFILE) -> None:
    """Create a sandbox profile layout without legacy runtime JSON files."""
    profile = _clean_profile_name(name)
    if profile == MAIN_PROFILE:
        raise ProfileSafetyError("Main profile cannot be created as a sandbox.")

    data_dir = get_profile_data_dir(profile)
    _ensure_profile_layout(data_dir)
    meta_path = _profile_meta_path(profile)
    if meta_path.is_file() is False:
        _write_json(
            meta_path,
            {
                "name": profile,
                "kind": SANDBOX_KIND,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )


def _backup_root() -> Path:
    return _base_data_dir() / "backups" / "profiles"


def _safe_profile_dir(name: str) -> Path:
    profile = _clean_profile_name(name)
    if profile == MAIN_PROFILE:
        raise ProfileSafetyError("Main profile is protected.")

    data_dir = get_profile_data_dir(profile).resolve()
    root = _profiles_root().resolve()
    if data_dir == root or data_dir.is_relative_to(root) is False:
        raise ProfileSafetyError(f"Unsafe profile path: {data_dir}")
    return data_dir


def backup_profile(name: str) -> Path:
    """Copy a profile directory before destructive operations."""
    profile = _clean_profile_name(name)
    data_dir = _safe_profile_dir(profile)
    if data_dir.is_dir() is False:
        raise FileNotFoundError(f"Profile not found: {profile}")

    backup_dir = _backup_root()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = backup_dir / f"{profile}_{stamp}"
    shutil.copytree(data_dir, destination)
    if destination.is_dir() is False:
        raise ProfileError("Profile backup was not created.")
    return destination


def _assert_reset_allowed(name: str) -> str:
    profile = _clean_profile_name(name)
    if profile == MAIN_PROFILE:
        raise ProfileSafetyError("Main profile reset is forbidden.")
    if _profile_kind(profile) != SANDBOX_KIND:
        raise ProfileSafetyError(f"Profile is not marked as sandbox: {profile}")
    return profile


def reset_profile(name: str) -> Path:
    """Reset a sandbox profile to an empty state after creating a backup."""
    profile = _assert_reset_allowed(name)
    data_dir = _safe_profile_dir(profile)
    backup_path = backup_profile(profile)
    if backup_path.is_dir() is False:
        raise ProfileError("Profile backup was not created.")

    shutil.rmtree(data_dir)
    create_sandbox_profile(profile)
    if get_active_profile() == profile:
        apply_profile_to_constants(profile)
    return backup_path


def delete_profile(name: str) -> Path:
    """Delete an inactive sandbox profile after creating a backup."""
    profile = _assert_reset_allowed(name)
    if get_active_profile() == profile:
        raise ProfileSafetyError("Cannot delete the active sandbox profile.")

    data_dir = _safe_profile_dir(profile)
    backup_path = backup_profile(profile)
    if backup_path.is_dir() is False:
        raise ProfileError("Profile backup was not created.")
    shutil.rmtree(data_dir)
    return backup_path


def _with_sep(path: Path) -> str:
    return str(path) + os.sep


def _apply_module_level_path_caches(*, cache_dir: Path, posters_dir: Path, logs_dir: Path) -> None:
    poster_cache = sys.modules.get("posters.cache")
    if poster_cache is not None:
        poster_cache.DEFAULT_POSTER_CACHE_DIR = posters_dir
        poster_cache.DEFAULT_POSTER_CACHE_JSON = poster_cache.DEFAULT_POSTER_CACHE_DIR / "posters.json"
        poster_cache.DEFAULT_POSTER_IMAGES_DIR = poster_cache.DEFAULT_POSTER_CACHE_DIR / "images"

    poster_download = sys.modules.get("posters.download_images")
    if poster_download is not None:
        poster_download.DEFAULT_POSTER_IMAGES_DIR = posters_dir / "images"
        poster_download.PREVIEW_POSTER_DIR = poster_download.DEFAULT_POSTER_IMAGES_DIR / "preview"

    poster_jobs = sys.modules.get("posters.download_job")
    if poster_jobs is not None:
        poster_jobs.DEFAULT_JOBS_DIR = posters_dir / "jobs"

    tmdb_overrides = sys.modules.get("posters.tmdb_overrides")
    if tmdb_overrides is not None:
        tmdb_overrides.DEFAULT_TMDB_CACHE_DIR = cache_dir / "tmdb"
        tmdb_overrides.DEFAULT_WATCHED_TMDB_OVERRIDES_JSON = (
            tmdb_overrides.DEFAULT_TMDB_CACHE_DIR / "watched_tmdb_overrides.json"
        )

    tmdb_api = sys.modules.get("apis.tmdb_api")
    if tmdb_api is not None:
        tmdb_api.TMDB_CACHE_DIR = cache_dir / "tmdb"
        tmdb_api.DISCOVER_CACHE_DIR = tmdb_api.TMDB_CACHE_DIR / "discover"
        tmdb_api.DETAILS_CACHE_DIR = tmdb_api.TMDB_CACHE_DIR / "details"
        tmdb_api.GENRE_CACHE_DIR = tmdb_api.TMDB_CACHE_DIR / "genre"

    gui_event_log = sys.modules.get("diagnostics.gui_event_log")
    if gui_event_log is not None:
        gui_event_log.DEFAULT_GUI_LOG_DIR = logs_dir / "reports"


def apply_profile_to_constants(name: str) -> None:
    """Apply profile paths to legacy constant-based storage modules."""
    profile = _clean_profile_name(name)
    data_dir = get_profile_data_dir(profile)
    installed_paths = get_app_paths()
    if profile == MAIN_PROFILE and data_dir.resolve() == installed_paths.data_dir.resolve():
        cache_dir = installed_paths.cache_dir
        posters_dir = installed_paths.posters_dir
        exports_dir = installed_paths.exports_dir
        logs_dir = installed_paths.logs_dir
        backups_dir = installed_paths.backups_dir
        config_dir = installed_paths.config_dir
    else:
        cache_dir = data_dir / "cache"
        posters_dir = cache_dir / "posters"
        exports_dir = data_dir / "exports"
        logs_dir = data_dir / "logs"
        backups_dir = data_dir / "backups"
        config_dir = data_dir / "config"

    constant.APP_DATA_DIR = str(data_dir)
    constant.WATCHED_DIR = str(data_dir / "watched")
    constant.CANDIDATES_DIR = str(data_dir / "candidates")
    constant.CACHE_DIR = str(cache_dir)
    constant.POSTERS_DIR = str(posters_dir)
    constant.EXPORTS_DIR = str(exports_dir)
    constant.LOGS_DIR = str(logs_dir)
    constant.CONFIG_DIR = str(config_dir)
    constant.BACKUP_DIR = _with_sep(backups_dir)

    constant.DATA_DIR = constant.WATCHED_DIR
    constant.API_LOG_FILE = str(logs_dir / "api_requests.log")
    constant.DIR_META = constant.WATCHED_DIR
    constant.DIR_TXT = constant.EXPORTS_DIR
    _apply_module_level_path_caches(cache_dir=cache_dir, posters_dir=posters_dir, logs_dir=logs_dir)


def apply_active_profile_to_constants() -> None:
    """Apply the persisted active profile to legacy constant-based paths."""
    apply_profile_to_constants(get_active_profile())


def set_active_profile(name: str) -> None:
    """Persist and apply the active profile atomically enough for local CLI use."""
    profile = _clean_profile_name(name)
    if _profile_exists(profile) is False:
        raise FileNotFoundError(f"Profile not found: {profile}")

    active_path = _active_profile_path()
    _write_json(
        active_path,
        {
            "active_profile": profile,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    apply_profile_to_constants(profile)


def get_active_data_files() -> dict[str, Path]:
    """Return important data files for the active profile."""
    data_dir = get_active_data_dir()
    return _empty_profile_paths(data_dir) | {
        "active_profile": _active_profile_path(),
        "profile_data_dir": data_dir,
        "backups": data_dir / "backups",
    }


def describe_active_profile() -> dict[str, Any]:
    """Return a compact active profile description for console screens."""
    profile = get_active_profile()
    return {
        "profile": profile,
        "data_dir": get_profile_data_dir(profile),
        "files": get_active_data_files(),
    }
