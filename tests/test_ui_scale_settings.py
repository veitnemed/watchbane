import importlib
import json
import re
import sys
from pathlib import Path
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

SCALE_ANCHORS = (0.75, 1.0, 1.50)


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


def _set_anchor_ui_scale(ui_scale: float) -> None:
    import desktop.theme.scaling as scaling
    from desktop.theme.ui_modules import ensure_scaled_ui_modules

    scaling.set_ui_scale(ui_scale)
    scaling._scale_tuning = dict(DEFAULT_TUNING)
    ensure_scaled_ui_modules()


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


def test_font_scaling_uses_half_up_rounding_for_compact_scales() -> None:
    import desktop.theme.scaling as scaling

    scaling.set_ui_scale(0.75)
    scaling._scale_tuning = dict(DEFAULT_TUNING)

    assert scaling.font_px(14) == 11
    assert scaling.font_px(13) == 10
    assert scaling.font_px(12) == 9


def test_default_tuning_profile_values_match_base_tokens() -> None:
    import desktop.shared.detail.profiles as profiles
    from desktop.theme import layout
    from desktop.theme.scaling import set_ui_scale

    set_ui_scale(1.0)
    profiles = importlib.reload(profiles)

    assert profiles.LIST_ITEM_HEIGHT == 84
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_poster_width == layout.DETAIL_POSTER_WIDTH
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_poster_height == layout.DETAIL_POSTER_HEIGHT
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_rating_widget_size == layout.DETAIL_RATING_WIDGET_SIZE
    assert profiles.DETAIL_CARD_LAYOUT_PROFILE.detail_chip_height == layout.DETAIL_CHIP_HEIGHT


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


def test_range_slider_keeps_readable_minimum_at_compact_scale(qapp) -> None:
    import desktop.theme.scaling as scaling
    from desktop.shared.widgets.range_slider import RangeSlider

    scaling.set_ui_scale(0.75)
    scaling._scale_tuning = dict(DEFAULT_TUNING)

    slider = RangeSlider(0, 10, 0, 10)

    assert slider.minimumHeight() >= 34
    assert slider.sizeHint().height() >= 34


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


@pytest.mark.parametrize("ui_scale", SCALE_ANCHORS)
def test_scale_anchor_layout_constants_use_scaled_tokens(monkeypatch, ui_scale) -> None:
    import desktop.shell.main_window as main_window
    import desktop.theme.layout as layout
    import desktop.theme.shell_layout as shell_layout
    import desktop.theme.scaling as scaling
    from desktop.shared.detail import profiles

    _set_anchor_ui_scale(ui_scale)

    monkeypatch.setattr(main_window.QApplication, "primaryScreen", lambda: None)
    window_width, window_height = main_window.scaled_main_window_size()

    assert window_width == scaling.scale_px(main_window.MAIN_WINDOW_BASE_WIDTH)
    assert window_height == scaling.scale_px(main_window.MAIN_WINDOW_BASE_HEIGHT)
    assert window_width >= 800
    assert window_height >= 500

    assert profiles.LIST_ITEM_HEIGHT == scaling.list_px(layout.LIST_ITEM_HEIGHT_BASE)
    assert profiles.LIST_ITEM_HEIGHT >= 48
    assert profiles.LIST_THUMB_WIDTH > 0
    assert profiles.LIST_THUMB_HEIGHT > 0
    assert profiles.LIST_THUMB_HEIGHT < profiles.LIST_ITEM_HEIGHT

    assert shell_layout.SIDEBAR_MIN_WIDTH_PX == layout.SIDEBAR_MIN_WIDTH_PX
    assert shell_layout.SIDEBAR_MAX_WIDTH_PX == layout.SIDEBAR_MAX_WIDTH_PX
    assert shell_layout.SIDEBAR_MIN_WIDTH_PX == scaling.list_px(layout.SIDEBAR_MIN_WIDTH)
    assert shell_layout.SIDEBAR_MAX_WIDTH_PX == scaling.list_px(layout.SIDEBAR_MAX_WIDTH)
    assert shell_layout.SIDEBAR_MIN_WIDTH_PX >= 180
    assert shell_layout.SIDEBAR_MIN_WIDTH_PX < shell_layout.SIDEBAR_MAX_WIDTH_PX

    assert shell_layout.CANDIDATE_LIST_MIN_WIDTH_PX == layout.CANDIDATE_LIST_MIN_WIDTH_PX
    assert shell_layout.CANDIDATE_LIST_MAX_WIDTH_PX == layout.CANDIDATE_LIST_MAX_WIDTH_PX
    assert shell_layout.CANDIDATE_LIST_MIN_WIDTH_PX == scaling.list_px(layout.CANDIDATE_LIST_MIN_WIDTH)
    assert shell_layout.CANDIDATE_LIST_MAX_WIDTH_PX == scaling.list_px(layout.CANDIDATE_LIST_MAX_WIDTH)
    assert shell_layout.CANDIDATE_LIST_MIN_WIDTH_PX >= 180
    assert shell_layout.CANDIDATE_LIST_MIN_WIDTH_PX < shell_layout.CANDIDATE_LIST_MAX_WIDTH_PX

    watched_profile = profiles.DETAIL_CARD_LAYOUT_PROFILE
    candidate_profile = profiles.CANDIDATE_DETAIL_CARD_PROFILE
    preview_profile = profiles.ADD_TITLE_PREVIEW_CARD_PROFILE
    assert watched_profile.detail_poster_width == scaling.poster_px(layout.DETAIL_POSTER_WIDTH)
    assert watched_profile.detail_poster_height == scaling.poster_px(layout.DETAIL_POSTER_HEIGHT)
    assert watched_profile.detail_info_min_width == scaling.detail_px(layout.DETAIL_INFO_MIN_WIDTH)
    assert watched_profile.detail_poster_width >= 240
    assert watched_profile.detail_poster_height >= 360
    assert candidate_profile.detail_poster_width == watched_profile.detail_poster_width
    assert preview_profile.detail_poster_width > 0
    assert preview_profile.detail_poster_height > 0


@pytest.mark.parametrize("ui_scale", SCALE_ANCHORS)
def test_scale_anchor_widget_contract_properties(qapp, ui_scale) -> None:
    from PyQt6.QtWidgets import QLabel, QFrame, QLineEdit, QPushButton, QWidget

    _set_anchor_ui_scale(ui_scale)

    import desktop.candidates.filters_form as filters_form_module
    import desktop.candidates.filters_view as filters_view_module
    import desktop.candidates.list_view as list_view_module
    from desktop.candidates.session import CandidateSearchSession
    from desktop.shared.detail import DetailCard
    from desktop.shared.detail import profiles as detail_profiles
    import desktop.settings.tab_view as settings_tab_module
    from desktop.watched.filters_panel import WatchedFiltersPanel

    importlib.reload(filters_form_module)
    filters_view_module = importlib.reload(filters_view_module)
    list_view_module = importlib.reload(list_view_module)
    settings_tab_module = importlib.reload(settings_tab_module)

    APPLY_BUTTON_HEIGHT = filters_view_module.APPLY_BUTTON_HEIGHT
    CandidateFiltersView = filters_view_module.CandidateFiltersView
    CandidateListView = list_view_module.CandidateListView
    SettingsTabView = settings_tab_module.SettingsTabView

    class CandidateServiceStub:
        SEARCH_SORT_MODES = ("final_score",)
        SEARCH_SORT_MODE_LABELS = {"final_score": "Итог"}

        def get_search_overview_view(self):
            return {"is_empty": False, "summary": "ok", "candidates": [], "stats": {}}

        def get_search_filter_defaults_view(self):
            return {"defaults": {}}

        def get_search_filter_chip_options_view(self):
            return {
                "genres": [{"label": "Драма"}, {"label": "Комедия"}],
                "countries": [{"code": "US", "label": "США"}],
            }

        def get_pool_stats_view(self):
            return {"stats": {"unique_total": 0}}

    service = CandidateServiceStub()

    settings_view = SettingsTabView()
    restart_message = settings_view.widget.findChild(QLabel, "settingsRestartMessage")
    save_button = settings_view.widget.findChild(QPushButton, "saveSettingsButton")
    reset_button = settings_view.widget.findChild(QPushButton, "resetUiScaleButton")
    assert restart_message is not None
    assert restart_message.wordWrap() is True
    assert restart_message.isHidden() is True
    assert save_button is not None and save_button.sizeHint().height() >= 20
    assert reset_button is not None and reset_button.sizeHint().height() >= 20

    watched_filters = WatchedFiltersPanel([], on_filters_changed=lambda: None)
    assert watched_filters.panel.isHidden() is True
    watched_filters.toggle_panel()
    assert watched_filters.panel.isHidden() is False
    assert watched_filters._score_slider.minimumHeight() >= 34
    assert watched_filters._year_slider.minimumHeight() >= 34

    filters_session = CandidateSearchSession(service=service)
    filters_view = CandidateFiltersView(filters_session, service=service)
    assert filters_view._intro_lead.wordWrap() is True
    assert filters_view._intro_stats.wordWrap() is True
    assert filters_view._apply_button.height() == APPLY_BUTTON_HEIGHT
    assert filters_view._reset_button.height() == APPLY_BUTTON_HEIGHT
    assert filters_view._apply_button.height() >= 30
    assert filters_view._form.scroll.widgetResizable() is True
    assert filters_view._tmdb_score_slider.minimumHeight() >= 34
    assert filters_view._tmdb_votes_slider.minimumHeight() >= 34

    list_session = CandidateSearchSession(service=service)
    list_view = CandidateListView(list_session)
    list_panel = list_view.widget.findChild(QWidget, "candidateSearchResultsPanel")
    detail_placeholder = list_view.widget.findChild(QLabel, "candidateSearchDetailPlaceholder")
    search_input = list_view.widget.findChild(QLineEdit, "candidateListSearch")
    assert list_panel is not None
    assert list_panel.minimumWidth() >= 180
    assert list_panel.maximumWidth() > list_panel.minimumWidth()
    assert detail_placeholder is not None
    assert detail_placeholder.wordWrap() is True
    assert detail_placeholder.isHidden() is False
    assert search_input is not None
    assert search_input.sizeHint().height() >= 20

    for profile in (
        detail_profiles.DETAIL_CARD_LAYOUT_PROFILE,
        detail_profiles.CANDIDATE_DETAIL_CARD_PROFILE,
        detail_profiles.ADD_TITLE_PREVIEW_CARD_PROFILE,
    ):
        detail_card = DetailCard(profile=profile)
        hero = detail_card.widget
        poster = hero.findChild(QFrame, "detailPosterShell")
        title = hero.findChild(QLabel, "detailTitle")
        overview = hero.findChild(QLabel, "detailOverviewText")
        main_info = hero.findChild(QWidget, "detailMainInfoSection")
        toggle = hero.findChild(QPushButton, "detailMainInfoToggleButton")
        assert hero.objectName() == "detailHeroCard"
        assert poster is not None
        assert poster.minimumWidth() == profile.detail_poster_width
        assert poster.minimumHeight() == profile.detail_poster_height
        assert poster.minimumWidth() > 0
        assert poster.minimumHeight() > 0
        assert title is not None and title.wordWrap() is True
        assert overview is not None and overview.wordWrap() is True
        assert main_info is not None
        assert main_info.maximumWidth() == profile.detail_section_max_width
        assert toggle is not None and toggle.isHidden() is True


@pytest.mark.parametrize("ui_scale", SCALE_ANCHORS)
def test_scale_anchor_add_title_dialog_contract_properties(qapp, ui_scale) -> None:
    from PyQt6.QtWidgets import QLabel, QLineEdit, QPushButton

    _set_anchor_ui_scale(ui_scale)

    from dataset.add_flow.bundle import AddTitleResolveBundle
    import desktop.watched.add_title.constants as add_title_constants
    import desktop.watched.add_title.preview_dialog as preview_dialog_module
    import desktop.watched.add_title.search_dialog as search_dialog_module

    add_title_constants = importlib.reload(add_title_constants)
    search_dialog_module = importlib.reload(search_dialog_module)
    preview_dialog_module = importlib.reload(preview_dialog_module)

    AddTitleSearchDialog = search_dialog_module.AddTitleSearchDialog
    AddTitlePreviewDialog = preview_dialog_module.AddTitlePreviewDialog
    PREVIEW_DIALOG_HEIGHT = add_title_constants.PREVIEW_DIALOG_HEIGHT
    PREVIEW_DIALOG_WIDTH = add_title_constants.PREVIEW_DIALOG_WIDTH
    SEARCH_DIALOG_HEIGHT = add_title_constants.SEARCH_DIALOG_HEIGHT
    SEARCH_DIALOG_HEIGHT_ACTIVE = add_title_constants.SEARCH_DIALOG_HEIGHT_ACTIVE
    SEARCH_DIALOG_WIDTH = add_title_constants.SEARCH_DIALOG_WIDTH

    search_dialog = AddTitleSearchDialog(initial_title="Long title")
    subtitle = search_dialog.findChild(QLabel, "addTitleSubtitle")
    status = search_dialog.findChild(QLabel, "addTitleStatus")
    title_input = search_dialog.findChild(QLineEdit, "addTitleSearchInput")
    search_button = search_dialog.findChild(QPushButton, "addTitleSearchButton")
    assert search_dialog.minimumWidth() == SEARCH_DIALOG_WIDTH
    assert search_dialog.height() == SEARCH_DIALOG_HEIGHT
    assert subtitle is not None and subtitle.wordWrap() is True
    assert status is not None and status.wordWrap() is True
    assert title_input is not None and title_input.sizeHint().height() >= 24
    assert search_button is not None and search_button.sizeHint().height() >= 24

    search_dialog._set_search_active(True)
    assert search_dialog.height() == SEARCH_DIALOG_HEIGHT_ACTIVE
    assert status.isHidden() is False
    search_dialog.close()

    bundle = AddTitleResolveBundle(
        title="Long Preview Title",
        country="",
        defaults={"main_info": {"title": "Long Preview Title", "year": 2020}, "raw_scores": {}, "genre": {}},
        meta_payload={},
        poster_hints={},
        preview_movie={"main_info": {"title": "Long Preview Title", "year": 2020}},
        preview_card={"title": "Long Preview Title", "year": 2020, "genres": ["Драма", "Комедия"]},
        found=True,
        statuses={},
    )
    preview_dialog = AddTitlePreviewDialog(bundle)
    warning = preview_dialog.findChild(QLabel, "addTitleWarning")
    confirm_hint = preview_dialog.findChild(QLabel, "addTitleConfirmHint")
    confirm_button = preview_dialog.findChild(QPushButton, "addTitleConfirmButton")
    back_button = preview_dialog.findChild(QPushButton, "addTitleSecondaryButton")
    assert preview_dialog.minimumWidth() == PREVIEW_DIALOG_WIDTH
    assert preview_dialog.height() == PREVIEW_DIALOG_HEIGHT
    assert warning is not None and warning.wordWrap() is True
    assert confirm_hint is not None and confirm_hint.wordWrap() is True
    assert confirm_button is not None and confirm_button.sizeHint().height() >= 24
    assert back_button is not None and back_button.sizeHint().height() >= 24
    preview_dialog.close()


def test_hardcoded_px_guard_for_direct_sizing_calls() -> None:
    pattern = re.compile(
        r"\.set(?:Fixed|Minimum)(?:Width|Height)\(\s*(?:[1-9][0-9]*|0)\s*\)"
    )
    # TODO: retire these legacy direct pixel calls by routing them through tokens/scaling helpers.
    legacy_whitelist = {
        ("desktop/analytics/sections/fallback_bars.py", "count.setFixedWidth(92)"),
        ("desktop/shared/detail/card.py", "self._genre_section.setFixedHeight(0)"),
        ("desktop/shared/widgets/country_chip_selector.py", "chip.setMinimumHeight(36)"),
        ("desktop/shared/widgets/genre_chip_selector.py", "chip.setMinimumHeight(36)"),
    }
    findings = set()

    for path in Path("desktop").rglob("*.py"):
        normalized_path = path.as_posix()
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if pattern.search(stripped):
                findings.add((normalized_path, stripped))

    assert findings == legacy_whitelist


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
    from desktop.theme.tokens import COLOR_SURFACE
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
    assert "QLineEdit#watchedSearch" in watched_style
    assert "QFrame#watchedScoreFilter" in watched_style
    assert f"background-color: {COLOR_SURFACE}" in watched_style
    assert f"min-height: {scaling.layout_px(34)}px" in watched_style
    assert f"min-height: {scaling.control_px(WATCHED_ADD_TITLE_MIN_HEIGHT)}px" in watched_style
    assert f"font-size: {scaling.font_px(WATCHED_SIDEBAR_LABEL_FONT)}px" in watched_style


def test_app_style_includes_settings_scaled_typography() -> None:
    import desktop.theme.scaling as scaling
    from desktop.theme.styles.app import build_app_style
    from desktop.theme.tokens import FONT_BASE, FONT_SECTION, FONT_TITLE

    scaling.set_ui_scale(0.75)
    scaling._scale_tuning = dict(DEFAULT_TUNING)

    style = build_app_style()

    assert "QWidget#settingsTabRoot" in style
    assert "QFrame#settingsInterfaceSection" in style
    assert "QLabel#uiScaleLabel" in style
    assert "QPushButton#saveSettingsButton" in style
    assert f"font-size: {scaling.font_px(FONT_BASE)}px" in style
    assert f"font-size: {scaling.font_px(FONT_SECTION)}px" in style
    assert f"font-size: {scaling.font_px(FONT_TITLE)}px" in style
