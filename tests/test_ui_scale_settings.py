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


def test_scaling_module_import_does_not_eager_load_settings_ui() -> None:
    import desktop.theme.scaling as scaling

    assert scaling.get_ui_scale() == 1.0


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

    assert profiles.LIST_ITEM_HEIGHT == 84
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width == tokens.DETAIL_POSTER_WIDTH
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_poster_height == tokens.DETAIL_POSTER_HEIGHT
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_rating_widget_size == tokens.DETAIL_RATING_WIDGET_SIZE
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_chip_height == tokens.DETAIL_CHIP_HEIGHT


def test_local_ui_tuning_is_gitignored() -> None:
    from pathlib import Path

    assert "desktop/theme/local_ui_tuning.py" in Path(".gitignore").read_text(encoding="utf-8")


def test_ensure_scaled_ui_modules_reloads_early_imported_profiles() -> None:
    import importlib

    import desktop.shared.detail.profiles as profiles
    import desktop.theme.scaling as scaling
    from desktop.theme.ui_modules import ensure_scaled_ui_modules

    scaling.set_ui_scale(1.0)
    scaling._scale_tuning = dict(DEFAULT_TUNING)
    importlib.import_module("desktop.shared.detail.profiles")
    assert profiles.LIST_ITEM_HEIGHT == 84

    scaling.set_ui_scale(0.75)
    ensure_scaled_ui_modules()

    assert profiles.LIST_ITEM_HEIGHT == 63


def test_bootstrap_uses_app_scale_without_qt_scale_factor() -> None:
    import inspect

    import desktop.shell.bootstrap as bootstrap

    source = inspect.getsource(bootstrap)

    assert "QT_SCALE_FACTOR" not in source
    assert "get_persisted_ui_scale" in source
    assert "set_ui_scale(" in source
    assert "font_px(FONT_APP)" in source
    assert "ensure_scaled_ui_modules" in inspect.getsource(bootstrap.main)


def test_tmdb_ring_value_font_scales_with_ui_scale(qapp) -> None:
    import desktop.theme.scaling as scaling
    from desktop.shared.detail.card_pills import make_meta_pill
    from desktop.shared.detail.profiles import DETAIL_CARD_LAYOUT_PROFILE

    scaling.set_ui_scale(1.0)
    scaling._scale_tuning = dict(DEFAULT_TUNING)
    ring_100 = make_meta_pill(
        {
            "display_value": "7.4",
            "display_label": "TMDb",
            "ring_progress": 0.74,
            "source": "tmdb",
        },
        DETAIL_CARD_LAYOUT_PROFILE,
    )

    scaling.set_ui_scale(0.75)
    ring_75 = make_meta_pill(
        {
            "display_value": "7.4",
            "display_label": "TMDb",
            "ring_progress": 0.74,
            "source": "tmdb",
        },
        DETAIL_CARD_LAYOUT_PROFILE,
    )

    assert ring_100._value_font_point == 24
    assert ring_75._value_font_point == 18
    assert ring_75._value_font_point < ring_100._value_font_point


def test_candidate_detail_card_profile_scales_with_ui_scale(qapp) -> None:
    import desktop.settings.app_settings  # noqa: F401 — preload before theme.shared imports
    import desktop.theme.scaling as scaling
    from desktop.shared.detail import profiles as detail_profiles
    from desktop.theme.ui_modules import ensure_scaled_ui_modules

    scaling.set_ui_scale(1.0)
    scaling._scale_tuning = dict(DEFAULT_TUNING)
    ensure_scaled_ui_modules()
    width_100 = detail_profiles.CANDIDATE_DETAIL_CARD_PROFILE.detail_poster_width

    scaling.set_ui_scale(0.75)
    ensure_scaled_ui_modules()
    width_75 = detail_profiles.CANDIDATE_DETAIL_CARD_PROFILE.detail_poster_width

    assert width_75 < width_100
    assert width_75 == scaling.poster_px(360)


def test_settings_dialog_displays_current_scale(monkeypatch, tmp_path, qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QSlider

    from desktop.settings.dialog import SettingsDialog

    _use_settings_path(monkeypatch, tmp_path)
    save_app_settings(AppSettings(ui_scale=1.25))

    dialog = SettingsDialog()
    slider = dialog.findChild(QSlider, "uiScaleSlider")
    value_label = dialog.findChild(QLabel, "uiScaleValueLabel")

    assert slider is not None
    assert slider.value() == 125
    assert value_label is not None
    assert value_label.text() == "125%"


def test_settings_dialog_selecting_125_saves_ui_scale(monkeypatch, tmp_path, qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QPushButton, QSlider

    from desktop.settings.dialog import SettingsDialog, UI_SCALE_RESTART_MESSAGE

    _use_settings_path(monkeypatch, tmp_path)
    dialog = SettingsDialog()
    slider = dialog.findChild(QSlider, "uiScaleSlider")
    save_button = dialog.findChild(QPushButton, "saveSettingsButton")
    message_label = dialog.findChild(QLabel, "settingsRestartMessage")
    messages = []
    dialog.settingsSaved.connect(messages.append)

    slider.setValue(125)
    save_button.click()

    assert load_app_settings().ui_scale == 1.25
    assert dialog.restart_message == UI_SCALE_RESTART_MESSAGE
    assert message_label.text() == UI_SCALE_RESTART_MESSAGE
    assert messages == [UI_SCALE_RESTART_MESSAGE]


def test_settings_dialog_reset_prepares_and_saves_default_scale(monkeypatch, tmp_path, qapp) -> None:
    from PyQt6.QtWidgets import QPushButton, QSlider

    from desktop.settings.dialog import SettingsDialog

    _use_settings_path(monkeypatch, tmp_path)
    save_app_settings(AppSettings(ui_scale=1.35))
    dialog = SettingsDialog()
    slider = dialog.findChild(QSlider, "uiScaleSlider")
    reset_button = dialog.findChild(QPushButton, "resetUiScaleButton")
    save_button = dialog.findChild(QPushButton, "saveSettingsButton")

    reset_button.click()

    assert slider.value() == 100

    save_button.click()

    assert load_app_settings().ui_scale == 1.0


def test_settings_tab_uses_slider_scale_control() -> None:
    import inspect

    import desktop.settings.tab_view as tab_module
    import desktop.shell.tabs as tabs_module

    tab_source = inspect.getsource(tab_module.SettingsTabView)
    factory_source = inspect.getsource(tabs_module.build_main_tabs)

    assert "UiScaleControlPanel" in tab_source
    assert "uiScaleSlider" not in tab_source
    assert '"Настройки"' in factory_source
    assert "SettingsTabView" in factory_source
    assert '"Информация"' not in factory_source
    assert "AnalyticsView" not in factory_source
    assert "on_watched_entries_changed" not in factory_source


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


@pytest.mark.parametrize(
    ("ui_scale", "base", "channel", "expected"),
    [
        (0.5, 100, "layout", 50),
        (1.0, 100, "layout", 100),
        (1.25, 100, "layout", 125),
        (2.0, 100, "layout", 200),
    ],
)
def test_layout_px_scales_with_ui_scale(ui_scale, base, channel, expected) -> None:
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(ui_scale)
    scaling._scale_tuning = dict(DEFAULT_TUNING)

    assert scaling.scale_px(base, channel=channel) == expected


def test_ui_scale_125_updates_shell_and_list_constants() -> None:
    import importlib

    import desktop.shared.detail.profiles as profiles
    import desktop.theme.scaling as scaling
    import desktop.theme.shell_layout as shell_layout

    scaling.set_ui_scale(1.25)
    scaling._scale_tuning = dict(DEFAULT_TUNING)
    shell_layout = importlib.reload(shell_layout)
    profiles = importlib.reload(profiles)

    assert shell_layout.SIDEBAR_MIN_WIDTH_PX == 375
    assert shell_layout.SIDEBAR_MAX_WIDTH_PX == shell_layout.CANDIDATE_LIST_MAX_WIDTH_PX
    assert shell_layout.SPLITTER_SIDEBAR_DEFAULT_PX == shell_layout.CANDIDATE_LIST_MAX_WIDTH_PX
    assert shell_layout.DETAIL_TAB_TOP_MARGIN_PX == 0
    assert shell_layout.LEFT_PANEL_TOP_COMPENSATION_PX > shell_layout.MAIN_TAB_PANE_TOP_LIFT_PX
    assert profiles.LIST_ITEM_HEIGHT == 105
    assert profiles.LIST_TITLE_FONT_POINT == 18


def test_ui_scale_125_updates_analytics_chart_height() -> None:
    import importlib

    import desktop.analytics.charts as charts
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(1.25)
    scaling._scale_tuning = dict(DEFAULT_TUNING)
    charts = importlib.reload(charts)

    assert charts.CHART_BASE_HEIGHT == 350


def test_shell_tabs_and_add_title_use_control_scaled_typography() -> None:
    import desktop.theme.scaling as scaling
    from desktop.theme.styles.shell import build_shell_style
    from desktop.theme.styles.watched_shell import build_watched_shell_style
    from desktop.theme.tokens import (
        FONT_BASE,
        FONT_SECTION,
        WATCHED_ADD_TITLE_MIN_HEIGHT,
        WATCHED_SIDEBAR_LABEL_FONT,
    )

    scaling.set_ui_scale(0.83)
    shell_style = build_shell_style()
    watched_style = build_watched_shell_style()

    assert f"font-size: {scaling.font_px(FONT_BASE)}px" in shell_style
    assert f"min-height: {scaling.control_px(34)}px" in shell_style
    assert f"font-size: {scaling.font_px(FONT_SECTION)}px" in watched_style
    assert f"min-height: {scaling.control_px(WATCHED_ADD_TITLE_MIN_HEIGHT)}px" in watched_style
    assert f"font-size: {scaling.font_px(WATCHED_SIDEBAR_LABEL_FONT)}px" in watched_style
