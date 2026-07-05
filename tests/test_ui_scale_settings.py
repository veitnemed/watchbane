import importlib
import json
import sys

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


@pytest.fixture(autouse=True)
def _reset_ui_scale():
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(1.0)
    yield
    scaling.set_ui_scale(1.0)
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


def test_env_override_is_current_process_only(monkeypatch, tmp_path) -> None:
    settings_path = _use_settings_path(monkeypatch, tmp_path)
    save_app_settings(AppSettings(ui_scale=1.10))

    monkeypatch.setenv("WATCHBANE_UI_SCALE", "1.35")

    assert get_persisted_ui_scale() == 1.35
    assert json.loads(settings_path.read_text(encoding="utf-8"))["ui_scale"] == 1.10


def test_scaling_default_ui_scale_is_one() -> None:
    import desktop.theme.scaling as scaling

    scaling = importlib.reload(scaling)

    assert scaling.get_ui_scale() == 1.0


def test_scaling_helpers_use_current_ui_scale() -> None:
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(1.25)
    assert scaling.scale_px(100) == 125

    scaling.set_ui_scale(0.85)
    assert scaling.scale_px(100) == 85
    assert scaling.scale_px(0) == 0

    scaling.set_ui_scale("bad")
    assert scaling.get_ui_scale() == 1.0

    scaling.set_ui_scale(2.0)
    assert scaling.get_ui_scale() == 2.00
    assert scaling.scale_px(100) == 200

    scaling.set_ui_scale(0.5)
    assert scaling.get_ui_scale() == 0.50
    assert scaling.scale_px(100) == 50
    assert scaling.scale_px(1) == 1


def test_bootstrap_uses_app_scale_without_qt_scale_factor() -> None:
    import inspect

    import desktop.shell.bootstrap as bootstrap

    source = inspect.getsource(bootstrap)

    assert "QT_SCALE_FACTOR" not in source
    assert "get_persisted_ui_scale" not in source
    assert "load_app_settings" in source
    assert "set_ui_scale(" in source
    assert "scale_font(10)" in source


def test_build_app_style_uses_current_ui_scale() -> None:
    from desktop.theme.scaling import set_ui_scale
    from desktop.theme.styles.app import build_app_style

    set_ui_scale(1.25)
    style = build_app_style()

    assert "font-size: 16px;" in style
    assert "border-radius: 15px;" in style


def test_detail_profile_default_scale_matches_base_values() -> None:
    import desktop.shared.detail.profiles as profiles
    from desktop.theme import tokens
    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(1.0)
    profiles = importlib.reload(profiles)

    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width == tokens.DETAIL_POSTER_WIDTH
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_poster_height == tokens.DETAIL_POSTER_HEIGHT
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_rating_widget_size == tokens.DETAIL_RATING_WIDGET_SIZE
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_chip_height == tokens.DETAIL_CHIP_HEIGHT


def test_detail_profile_scales_visual_values() -> None:
    import desktop.shared.detail.profiles as profiles
    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(1.25)
    profiles = importlib.reload(profiles)

    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width == 450
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_poster_height == 662
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_rating_widget_size == 170
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_chip_height == 45


def test_main_window_initial_size_scales(monkeypatch) -> None:
    from PyQt6.QtCore import QRect

    import desktop.shell.main_window as main_window
    from desktop.theme.scaling import set_ui_scale

    class _Screen:
        def availableGeometry(self):
            return QRect(0, 0, 4000, 3000)

    set_ui_scale(1.25)
    monkeypatch.setattr(main_window.QApplication, "primaryScreen", lambda: _Screen())

    assert main_window.scaled_main_window_size() == (1475, 900)


def test_missing_app_settings_load_does_not_crash(monkeypatch, tmp_path) -> None:
    _use_settings_path(monkeypatch, tmp_path)

    assert load_app_settings() == AppSettings()


def test_settings_dialog_displays_current_scale(monkeypatch, tmp_path, qapp) -> None:
    from PyQt6.QtWidgets import QComboBox

    from desktop.settings.dialog import SettingsDialog

    _use_settings_path(monkeypatch, tmp_path)
    save_app_settings(AppSettings(ui_scale=1.25))

    dialog = SettingsDialog()
    combo = dialog.findChild(QComboBox, "uiScaleComboBox")

    assert combo is not None
    assert combo.currentText() == "125%"


def test_settings_dialog_includes_full_scale_range(monkeypatch, tmp_path, qapp) -> None:
    from PyQt6.QtWidgets import QComboBox

    from desktop.settings.dialog import SettingsDialog

    _use_settings_path(monkeypatch, tmp_path)
    dialog = SettingsDialog()
    combo = dialog.findChild(QComboBox, "uiScaleComboBox")

    assert combo is not None
    assert [combo.itemText(index) for index in range(combo.count())] == [
        "50%",
        "75%",
        "85%",
        "100%",
        "110%",
        "125%",
        "135%",
        "150%",
        "175%",
        "200%",
    ]


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


def test_settings_action_opens_dialog(monkeypatch, qapp) -> None:
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import QDialog

    import desktop.shell.main_window as main_window

    opened = []

    class _Signal:
        def connect(self, callback):
            self._callback = callback

    class _Dialog:
        def __init__(self, parent=None) -> None:
            self.parent = parent
            self.restart_message = ""
            self.settingsSaved = _Signal()

        def exec(self):
            opened.append(self.parent)
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(main_window, "SettingsDialog", _Dialog)

    window = main_window.WatchedMoviesWindow(initial_size=(800, 600))
    action = window.findChild(QAction, "settingsAction")

    assert action is not None

    action.trigger()

    assert opened == [window]


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

    bootstrap.log_startup_scale_diagnostics(
        _App(),
        persisted_ui_scale=1.25,
        requested_initial_size=(1475, 900),
    )

    assert events[0][0] == "app.ui_scale.diagnostics"
    assert events[0][1]["persisted_ui_scale"] == 1.25
    assert events[0][1]["primary_screen_logical_dpi"] is None
    assert events[0][1]["primary_screen_device_pixel_ratio"] is None
    assert events[0][1]["primary_screen_available_geometry"] is None
    assert events[0][1]["requested_initial_window_size"] == {"width": 1475, "height": 900}
