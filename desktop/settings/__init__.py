"""Desktop application settings."""

from desktop.settings.app_settings import (
    APP_UI_SCALE_DEFAULT,
    APP_UI_SCALE_MAX,
    APP_UI_SCALE_MIN,
    APP_UI_SCALE_PRESETS,
    AppSettings,
    get_persisted_ui_scale,
    load_app_settings,
    normalize_ui_scale,
    save_app_settings,
)
from desktop.settings.dialog import SettingsDialog, UI_SCALE_OPTIONS, UI_SCALE_RESTART_MESSAGE

__all__ = [
    "APP_UI_SCALE_DEFAULT",
    "APP_UI_SCALE_MAX",
    "APP_UI_SCALE_MIN",
    "APP_UI_SCALE_PRESETS",
    "AppSettings",
    "get_persisted_ui_scale",
    "load_app_settings",
    "normalize_ui_scale",
    "save_app_settings",
    "SettingsDialog",
    "UI_SCALE_OPTIONS",
    "UI_SCALE_RESTART_MESSAGE",
]
