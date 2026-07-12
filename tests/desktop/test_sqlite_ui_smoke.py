from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidget, QTabWidget

from desktop.settings.app_settings import AppSettings, save_app_settings
from storage import data as storage_data
from storage import runtime


def _movie(title: str, year: int = 2024) -> dict:
    return {
        "main_info": {
            "title": title,
            "year": year,
            "user_score": 8.0,
            "country": "US",
            "media_type": "tv",
        },
        "raw_scores": {},
        "computed_scores": {},
        "genre": {},
    }


def test_main_window_loads_watched_tab_from_sqlite(qtbot) -> None:
    runtime.ensure_runtime_data_layout()
    save_app_settings(AppSettings(interface_language="en", data_language="en"))
    storage_data.save_dataset({"Alpha": _movie("Alpha")})

    from desktop.shell.main_window import WatchedMoviesWindow

    window = WatchedMoviesWindow(initial_size=(900, 600))
    qtbot.addWidget(window)
    window.show()

    tabs = window.findChild(QTabWidget, "mainTabs")
    watched_list = window.findChild(QListWidget, "watchedList")

    assert tabs is not None
    assert watched_list is not None
    assert tabs.count() == 4
    assert watched_list.count() == 1

    first_item = watched_list.item(0)
    entry = first_item.data(Qt.ItemDataRole.UserRole)
    assert entry[0] == "Alpha"
    assert entry[2]["title"] == "Alpha"


def test_main_window_resize_updates_both_responsive_tabs(qtbot) -> None:
    from desktop.shell.main_window import WatchedMoviesWindow
    from desktop.theme.shell_layout import (
        CANDIDATE_DETAIL_COLLAPSE_WIDTH_PX,
        WATCHED_DETAIL_COLLAPSE_WIDTH_PX,
    )

    window = WatchedMoviesWindow(initial_size=(900, 600))
    qtbot.addWidget(window)
    window.show()
    watched_view = window._tab_registry._specs["watched"].view
    candidate_view = window._tab_registry._specs["candidates"].view

    compact_width = min(
        WATCHED_DETAIL_COLLAPSE_WIDTH_PX,
        CANDIDATE_DETAIL_COLLAPSE_WIDTH_PX,
    ) - 1
    expanded_width = 1280
    assert max(WATCHED_DETAIL_COLLAPSE_WIDTH_PX, CANDIDATE_DETAIL_COLLAPSE_WIDTH_PX) < expanded_width

    for compact, width in (
        (True, compact_width),
        (False, expanded_width),
        (True, compact_width),
        (False, expanded_width),
    ):
        window.resize(width, 800)
        qtbot.waitUntil(lambda: watched_view._is_compact_layout is compact)
        qtbot.waitUntil(lambda: candidate_view._is_compact_layout is compact)
        assert watched_view._right_panel.isHidden() is compact
        assert candidate_view._detail_panel.isHidden() is compact

    window._tab_registry.focus("watched")
    assert watched_view._right_panel.isVisible()
    window._tab_registry.focus("candidates")
    assert candidate_view._detail_panel.isHidden() is False


def test_stale_resize_event_uses_current_window_width(qtbot) -> None:
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QResizeEvent

    from desktop.shell.main_window import WatchedMoviesWindow
    from desktop.theme.shell_layout import (
        CANDIDATE_DETAIL_COLLAPSE_WIDTH_PX,
        WATCHED_DETAIL_COLLAPSE_WIDTH_PX,
    )

    window = WatchedMoviesWindow(initial_size=(1280, 700))
    qtbot.addWidget(window)
    window.show()
    watched_view = window._tab_registry._specs["watched"].view
    candidate_view = window._tab_registry._specs["candidates"].view
    compact_width = min(
        WATCHED_DETAIL_COLLAPSE_WIDTH_PX,
        CANDIDATE_DETAIL_COLLAPSE_WIDTH_PX,
    ) - 1
    qtbot.waitUntil(lambda: window.width() >= 1280)
    qtbot.waitUntil(lambda: watched_view._is_compact_layout is False)
    qtbot.waitUntil(lambda: candidate_view._is_compact_layout is False)

    stale_event = QResizeEvent(
        QSize(compact_width, window.height()),
        QSize(window.width(), window.height()),
    )
    window.resizeEvent(stale_event)
    assert window.width() >= 1280
    assert watched_view._is_compact_layout is False
    assert candidate_view._is_compact_layout is False

    window._tab_registry.focus("settings")
    window._tab_registry.focus("candidates")
    assert candidate_view._detail_panel.isHidden() is False
    assert candidate_view._splitter.sizes()[1] > 0

    window._tab_registry.focus("watched")
    assert watched_view._right_panel.isVisible() is True
    assert watched_view._splitter.sizes()[1] > 0
