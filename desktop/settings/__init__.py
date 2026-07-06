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


def __getattr__(name: str):
    if name == "SettingsDialog":
        from desktop.settings.dialog import SettingsDialog

        return SettingsDialog
    if name == "SettingsTabView":
        from desktop.settings.tab_view import SettingsTabView

        return SettingsTabView
    if name == "UI_SCALE_RESTART_MESSAGE":
        from desktop.settings.ui_scale_control import UI_SCALE_RESTART_MESSAGE

        return UI_SCALE_RESTART_MESSAGE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
