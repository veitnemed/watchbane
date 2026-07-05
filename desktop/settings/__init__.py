"""Desktop application settings."""

from desktop.settings.app_settings import (
    APP_UI_SCALE_DEFAULT,
    APP_UI_SCALE_ENV,
    APP_UI_SCALE_MAX,
    APP_UI_SCALE_MIN,
    APP_UI_SCALE_PRESETS,
    AppSettings,
    get_persisted_ui_scale,
    load_app_settings,
    normalize_ui_scale,
    save_app_settings,
)
from desktop.settings.dialog import SettingsDialog
from desktop.settings.tab_view import SettingsTabView
from desktop.settings.ui_scale_control import UI_SCALE_RESTART_MESSAGE

__all__ = [
    "APP_UI_SCALE_DEFAULT",
    "APP_UI_SCALE_ENV",
    "APP_UI_SCALE_MAX",
    "APP_UI_SCALE_MIN",
    "APP_UI_SCALE_PRESETS",
    "AppSettings",
    "SettingsDialog",
    "SettingsTabView",
    "UI_SCALE_RESTART_MESSAGE",
    "get_persisted_ui_scale",
    "load_app_settings",
    "normalize_ui_scale",
    "save_app_settings",
]
