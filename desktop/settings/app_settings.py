"""Persistent desktop application settings."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
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


@dataclass(frozen=True)
class AppSettings:
    ui_scale: float = APP_UI_SCALE_DEFAULT
    interface_language: str = APP_LANGUAGE_DEFAULT
    data_language: str = APP_LANGUAGE_DEFAULT


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


def _settings_path() -> Path:
    return Path(constant.APP_SETTINGS_JSON)


def _settings_from_payload(payload) -> AppSettings:
    if isinstance(payload, dict) is False:
        return AppSettings()
    return AppSettings(
        ui_scale=normalize_ui_scale(payload.get("ui_scale", APP_UI_SCALE_DEFAULT)),
        interface_language=normalize_language(payload.get("interface_language", APP_LANGUAGE_DEFAULT)),
        data_language=normalize_language(payload.get("data_language", APP_LANGUAGE_DEFAULT)),
    )


def load_app_settings() -> AppSettings:
    """Load persisted desktop settings, falling back to defaults on invalid input."""
    if app_settings_store.is_sqlite_settings_backend():
        return _settings_from_payload(app_settings_store.load_sqlite_settings_dict())

    path = _settings_path()
    if path.exists() is False:
        return AppSettings()

    try:
        with path.open("r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return AppSettings()

    return _settings_from_payload(payload)


def save_app_settings(settings: AppSettings) -> None:
    """Persist desktop settings with an atomic replace."""
    normalized = AppSettings(
        ui_scale=normalize_ui_scale(settings.ui_scale),
        interface_language=normalize_language(settings.interface_language),
        data_language=normalize_language(settings.data_language),
    )
    if app_settings_store.is_sqlite_settings_backend():
        app_settings_store.save_sqlite_settings_dict(asdict(normalized))
        return

    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(asdict(normalized), file, ensure_ascii=False, indent=4)
        file.write("\n")
    os.replace(temp_path, path)


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
