"""Persistent desktop application settings."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import math
import os
import re

from config import app_settings_store
from config import constant

APP_UI_SCALE_DEFAULT = 1.0
APP_UI_SCALE_MIN = 0.50
APP_UI_SCALE_MAX = 2.00
APP_UI_SCALE_PRESETS = (0.50, 0.75, 0.85, 1.0, 1.10, 1.25, 1.35, 1.50, 1.75, 2.00)
APP_UI_SCALE_ENV = "WATCHBANE_UI_SCALE"
APP_LANGUAGE_DEFAULT = "ru"
APP_LANGUAGE_SUPPORTED = ("ru", "en")
APP_INTERFACE_LANGUAGE_ENV = "WATCHBANE_INTERFACE_LANGUAGE"
APP_DATA_LANGUAGE_ENV = "WATCHBANE_DATA_LANGUAGE"
APP_SETTINGS_SCHEMA_KEY = "desktop_app_settings_schema_version"
APP_SETTINGS_SCHEMA_VERSION = 1


APP_AUTO_POOL_REFILL_DEFAULT = True
APP_FTS_SEARCH_DEFAULT = True


@dataclass(frozen=True)
class AppSettings:
    ui_scale: float = APP_UI_SCALE_DEFAULT
    interface_language: str = APP_LANGUAGE_DEFAULT
    data_language: str = APP_LANGUAGE_DEFAULT
    auto_pool_refill: bool = APP_AUTO_POOL_REFILL_DEFAULT
    fts_search_enabled: bool = APP_FTS_SEARCH_DEFAULT


def normalize_ui_scale(value) -> float:
    """Return a safe application UI scale."""
    if isinstance(value, bool) or value in (None, ""):
        return APP_UI_SCALE_DEFAULT

    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return APP_UI_SCALE_DEFAULT
        if re.fullmatch(r"[+-]?(\d+(\.\d+)?|\.\d+)", value) is None:
            return APP_UI_SCALE_DEFAULT

    try:
        scale = float(value)
    except (TypeError, ValueError):
        return APP_UI_SCALE_DEFAULT

    if math.isfinite(scale) is False:
        return APP_UI_SCALE_DEFAULT

    return max(APP_UI_SCALE_MIN, min(APP_UI_SCALE_MAX, scale))


def normalize_language(value) -> str:
    """Return a supported app language code."""
    if isinstance(value, bool) or value in (None, ""):
        return APP_LANGUAGE_DEFAULT
    text = str(value).strip().casefold()
    if text in APP_LANGUAGE_SUPPORTED:
        return text
    return APP_LANGUAGE_DEFAULT


def language_to_tmdb_locale(language: str) -> str:
    """Map an app data language to a TMDb locale."""
    return {
        "ru": "ru-RU",
        "en": "en-US",
    }[normalize_language(language)]


def normalize_auto_pool_refill(value) -> bool:
    """Return a safe auto pool refill flag."""
    if value in (None, ""):
        return APP_AUTO_POOL_REFILL_DEFAULT
    if isinstance(value, str):
        return value.strip().casefold() not in ("0", "false", "no", "off")
    return bool(value)


def normalize_fts_search_enabled(value) -> bool:
    """Return a safe FTS search flag."""
    if value in (None, ""):
        return APP_FTS_SEARCH_DEFAULT
    if isinstance(value, str):
        return value.strip().casefold() not in ("0", "false", "no", "off")
    return bool(value)


def _settings_from_payload(payload) -> AppSettings:
    if isinstance(payload, dict) is False:
        return AppSettings()
    return AppSettings(
        ui_scale=normalize_ui_scale(payload.get("ui_scale", APP_UI_SCALE_DEFAULT)),
        interface_language=normalize_language(payload.get("interface_language", APP_LANGUAGE_DEFAULT)),
        data_language=normalize_language(payload.get("data_language", APP_LANGUAGE_DEFAULT)),
        auto_pool_refill=normalize_auto_pool_refill(payload.get("auto_pool_refill", APP_AUTO_POOL_REFILL_DEFAULT)),
        fts_search_enabled=normalize_fts_search_enabled(
            payload.get("fts_search_enabled", APP_FTS_SEARCH_DEFAULT)
        ),
    )


def _canonical_settings_payload(settings: AppSettings) -> dict:
    return {
        **asdict(settings),
        APP_SETTINGS_SCHEMA_KEY: APP_SETTINGS_SCHEMA_VERSION,
    }


@lru_cache(maxsize=8)
def _load_app_settings_for_data_root(_data_root: str) -> AppSettings:
    payload = app_settings_store.load_sqlite_settings_dict()
    settings = _settings_from_payload(payload)
    canonical = _canonical_settings_payload(settings)
    corrections = {
        key: value
        for key, value in canonical.items()
        if payload.get(key) != value
    }
    if corrections:
        app_settings_store.save_sqlite_settings_dict(corrections)
    return settings


def invalidate_app_settings_cache() -> None:
    """Forget process-local settings after a write or runtime profile change."""
    _load_app_settings_for_data_root.cache_clear()


def load_app_settings() -> AppSettings:
    """Load persisted settings once per active runtime data root."""
    data_root = os.path.normcase(os.path.abspath(str(constant.APP_DATA_DIR)))
    return _load_app_settings_for_data_root(data_root)


def save_app_settings(settings: AppSettings) -> None:
    """Persist desktop settings in SQLite."""
    normalized = AppSettings(
        ui_scale=normalize_ui_scale(settings.ui_scale),
        interface_language=normalize_language(settings.interface_language),
        data_language=normalize_language(settings.data_language),
        auto_pool_refill=normalize_auto_pool_refill(settings.auto_pool_refill),
        fts_search_enabled=normalize_fts_search_enabled(settings.fts_search_enabled),
    )
    app_settings_store.save_sqlite_settings_dict(_canonical_settings_payload(normalized))
    invalidate_app_settings_cache()


def get_persisted_ui_scale() -> float:
    """Return the UI scale for the current process."""
    env_value = os.environ.get(APP_UI_SCALE_ENV)
    if env_value not in (None, ""):
        return normalize_ui_scale(env_value)
    return load_app_settings().ui_scale


def get_persisted_interface_language() -> str:
    """Return the interface language for the current process."""
    env_value = os.environ.get(APP_INTERFACE_LANGUAGE_ENV)
    if env_value not in (None, ""):
        return normalize_language(env_value)
    return load_app_settings().interface_language


def get_persisted_data_language() -> str:
    """Return the data language for the current process."""
    env_value = os.environ.get(APP_DATA_LANGUAGE_ENV)
    if env_value not in (None, ""):
        return normalize_language(env_value)
    return load_app_settings().data_language
