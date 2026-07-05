import importlib
import json
import sys
from types import SimpleNamespace

import pytest

from config import constant
from desktop.settings.app_settings import (
    APP_UI_SCALE_DEFAULT,
    APP_UI_SCALE_MAX,
    APP_UI_SCALE_MIN,
    AppSettings,
    get_persisted_ui_scale,
    load_app_settings,
    normalize_ui_scale,
    save_app_settings,
)


DEFAULT_TUNING = {
    "ui": 1.0,
    "font": 1.0,
    "layout": 1.0,
    "control": 1.0,
    "list": 1.0,
    "detail": 1.0,
    "poster": 1.0,
}


@pytest.fixture(autouse=True)
def _reset_ui_scale():
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(1.0)
    scaling._scale_tuning = dict(DEFAULT_TUNING)
    yield
    scaling.set_ui_scale(1.0)
    scaling._scale_tuning = dict(DEFAULT_TUNING)
    if "desktop.shared.detail.profiles" in sys.modules:
        importlib.reload(sys.modules["desktop.shared.detail.profiles"])


def _use_settings_path(monkeypatch, tmp_path):
    settings_path = tmp_path / "data" / "settings.json"
    monkeypatch.setattr(constant, "APP_SETTINGS_JSON", str(settings_path))
    return settings_path


def test_missing_settings_file_gives_default_ui_scale(monkeypatch, tmp_path) -> None:
    _use_settings_path(monkeypatch, tmp_path)

    assert load_app_settings().ui_scale == APP_UI_SCALE_DEFAULT


def test_missing_ui_scale_gives_default(monkeypatch, tmp_path) -> None:
    settings_path = _use_settings_path(monkeypatch, tmp_path)
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({"other": True}), encoding="utf-8")

    assert load_app_settings().ui_scale == APP_UI_SCALE_DEFAULT


def test_invalid_json_does_not_crash(monkeypatch, tmp_path) -> None:
    settings_path = _use_settings_path(monkeypatch, tmp_path)
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("{bad json", encoding="utf-8")

    assert load_app_settings().ui_scale == APP_UI_SCALE_DEFAULT


def test_invalid_ui_scale_value_defaults_or_clamps() -> None:
    assert normalize_ui_scale(None) == APP_UI_SCALE_DEFAULT
    assert normalize_ui_scale(True) == APP_UI_SCALE_DEFAULT
    assert normalize_ui_scale("not-a-number") == APP_UI_SCALE_DEFAULT
    assert normalize_ui_scale("1e2") == APP_UI_SCALE_DEFAULT
    assert normalize_ui_scale("0.5") == APP_UI_SCALE_MIN
    assert normalize_ui_scale("0.25") == APP_UI_SCALE_MIN
    assert normalize_ui_scale(2.0) == APP_UI_SCALE_MAX
    assert normalize_ui_scale(2.5) == APP_UI_SCALE_MAX
    assert normalize_ui_scale("1.25") == 1.25


def test_save_then_load_ui_scale(monkeypatch, tmp_path) -> None:
    settings_path = _use_settings_path(monkeypatch, tmp_path)

    save_app_settings(AppSettings(ui_scale=1.25))

    assert settings_path.exists()
    assert load_app_settings().ui_scale == 1.25


def test_watchbane_ui_scale_env_override_is_current_process_only(monkeypatch, tmp_path) -> None:
    settings_path = _use_settings_path(monkeypatch, tmp_path)
    save_app_settings(AppSettings(ui_scale=1.10))

    monkeypatch.setenv("WATCHBANE_UI_SCALE", "1.35")

    assert get_persisted_ui_scale() == 1.35
    assert json.loads(settings_path.read_text(encoding="utf-8"))["ui_scale"] == 1.10


def test_get_scale_tuning_defaults_when_local_file_is_missing(monkeypatch) -> None:
    import desktop.theme.ui_tuning as ui_tuning

    def _missing_module(name):
        raise ModuleNotFoundError(name=name)

    monkeypatch.setattr(ui_tuning.importlib, "import_module", _missing_module)

    assert ui_tuning.get_scale_tuning() == DEFAULT_TUNING


def test_get_scale_tuning_validates_invalid_values(monkeypatch) -> None:
    import desktop.theme.ui_tuning as ui_tuning

    local_module = SimpleNamespace(
        SCALE_TUNING_OVERRIDES={
            "font": "bad",
            "layout": None,
            "control": True,
            "list": "1e2",
            "detail": "",
            "poster": object(),
        }
    )
    monkeypatch.setattr(ui_tuning.importlib, "import_module", lambda name: local_module)

    assert ui_tuning.get_scale_tuning() == DEFAULT_TUNING


def test_get_scale_tuning_clamps_values(monkeypatch) -> None:
    import desktop.theme.ui_tuning as ui_tuning

    local_module = SimpleNamespace(
        SCALE_TUNING_OVERRIDES={
            "font": 0.25,
            "layout": "2.50",
            "control": 1.25,
            "unknown": 1.75,
        }
    )
    monkeypatch.setattr(ui_tuning.importlib, "import_module", lambda name: local_module)

    tuning = ui_tuning.get_scale_tuning()

    assert tuning["font"] == 0.50
    assert tuning["layout"] == 2.00
    assert tuning["control"] == 1.25
    assert "unknown" not in tuning


def test_scaling_default_ui_scale_is_one() -> None:
    import desktop.theme.scaling as scaling

    scaling = importlib.reload(scaling)
    scaling._scale_tuning = dict(DEFAULT_TUNING)

    assert scaling.get_ui_scale() == 1.0
    assert scaling.get_channel_scale("layout") == 1.0


def test_scale_px_keeps_old_layout_channel_compatibility() -> None:
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(1.25)
    scaling._scale_tuning = dict(DEFAULT_TUNING, layout=1.20)

    assert scaling.scale_px(100) == 150
    assert scaling.scale_px(0) == 0
    assert scaling.scale_px(1) == 2


def test_channel_wrappers_use_their_channels() -> None:
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(1.10)
    scaling._scale_tuning = {
        "ui": 1.0,
        "font": 1.20,
        "layout": 1.10,
        "control": 1.30,
        "list": 1.40,
        "detail": 1.50,
        "poster": 1.60,
    }

    assert scaling.layout_px(100) == 121
    assert scaling.control_px(100) == 143
    assert scaling.list_px(100) == 154
    assert scaling.detail_px(100) == 165
    assert scaling.poster_px(100) == 176
    assert scaling.font_px(10) == 13


def test_minimum_preserving_rounding_keeps_tiny_values_non_zero() -> None:
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(0.5)
    scaling._scale_tuning = dict(DEFAULT_TUNING, layout=0.5)

    assert scaling.scale_px(0) == 0
    assert scaling.scale_px(1) == 1
    assert scaling.scale_px(-1) == -1


def test_default_tuning_profile_values_match_base_tokens() -> None:
    import desktop.shared.detail.profiles as profiles
    from desktop.theme import tokens
    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(1.0)
    profiles = importlib.reload(profiles)

    assert profiles.LIST_ITEM_HEIGHT == 72
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width == tokens.DETAIL_POSTER_WIDTH
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_poster_height == tokens.DETAIL_POSTER_HEIGHT
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_rating_widget_size == tokens.DETAIL_RATING_WIDGET_SIZE
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_chip_height == tokens.DETAIL_CHIP_HEIGHT


def test_local_ui_tuning_is_gitignored() -> None:
    from pathlib import Path

    assert "desktop/theme/local_ui_tuning.py" in Path(".gitignore").read_text(encoding="utf-8")


def test_bootstrap_uses_app_scale_without_qt_scale_factor() -> None:
    import inspect

    import desktop.shell.bootstrap as bootstrap

    source = inspect.getsource(bootstrap)

    assert "QT_SCALE_FACTOR" not in source
    assert "get_persisted_ui_scale" in source
    assert "set_ui_scale(" in source
    assert "font_px(10)" in source


def test_settings_dialog_displays_current_scale(monkeypatch, tmp_path, qapp) -> None:
    from PyQt6.QtWidgets import QComboBox

    from desktop.settings.dialog import SettingsDialog

    _use_settings_path(monkeypatch, tmp_path)
    save_app_settings(AppSettings(ui_scale=1.25))

    dialog = SettingsDialog()
    combo = dialog.findChild(QComboBox, "uiScaleComboBox")

    assert combo is not None
    assert combo.currentText() == "125%"


def test_settings_dialog_selecting_125_saves_ui_scale(monkeypatch, tmp_path, qapp) -> None:
    from PyQt6.QtWidgets import QComboBox, QLabel, QPushButton

    from desktop.settings.dialog import SettingsDialog, UI_SCALE_RESTART_MESSAGE

    _use_settings_path(monkeypatch, tmp_path)
    dialog = SettingsDialog()
    combo = dialog.findChild(QComboBox, "uiScaleComboBox")
    save_button = dialog.findChild(QPushButton, "saveSettingsButton")
    message_label = dialog.findChild(QLabel, "settingsRestartMessage")
    messages = []
    dialog.settingsSaved.connect(messages.append)

    combo.setCurrentText("125%")
    save_button.click()

    assert load_app_settings().ui_scale == 1.25
    assert dialog.restart_message == UI_SCALE_RESTART_MESSAGE
    assert message_label.text() == UI_SCALE_RESTART_MESSAGE
    assert messages == [UI_SCALE_RESTART_MESSAGE]


def test_settings_dialog_reset_prepares_and_saves_default_scale(monkeypatch, tmp_path, qapp) -> None:
    from PyQt6.QtWidgets import QComboBox, QPushButton

    from desktop.settings.dialog import SettingsDialog

    _use_settings_path(monkeypatch, tmp_path)
    save_app_settings(AppSettings(ui_scale=1.35))
    dialog = SettingsDialog()
    combo = dialog.findChild(QComboBox, "uiScaleComboBox")
    reset_button = dialog.findChild(QPushButton, "resetUiScaleButton")
    save_button = dialog.findChild(QPushButton, "saveSettingsButton")

    reset_button.click()

    assert combo.currentText() == "100%"

    save_button.click()

    assert load_app_settings().ui_scale == 1.0


def test_startup_scale_diagnostics_handles_missing_screen(monkeypatch) -> None:
    import desktop.shell.bootstrap as bootstrap

    events = []

    class _Font:
        def family(self):
            return "Inter"

        def pointSize(self):
            return 12

    class _App:
        def font(self):
            return _Font()

        def primaryScreen(self):
            return None

    monkeypatch.setattr(
        bootstrap,
        "log_event",
        lambda event, **fields: events.append((event, fields)),
    )
    monkeypatch.setattr(bootstrap, "get_scale_tuning", lambda: dict(DEFAULT_TUNING))

    bootstrap.log_startup_scale_diagnostics(
        _App(),
        persisted_settings=AppSettings(ui_scale=1.10),
        active_ui_scale=1.25,
        requested_initial_size=(1475, 900),
    )

    assert events[0][0] == "app.ui_scale.diagnostics"
    assert events[0][1]["persisted_ui_scale"] == 1.10
    assert events[0][1]["active_process_ui_scale"] == 1.25
    assert events[0][1]["scale_tuning"] == DEFAULT_TUNING
    assert events[0][1]["primary_screen_logical_dpi"] is None
    assert events[0][1]["primary_screen_device_pixel_ratio"] is None
    assert events[0][1]["primary_screen_available_geometry"] is None
    assert events[0][1]["requested_initial_window_size"] == {"width": 1475, "height": 900}
