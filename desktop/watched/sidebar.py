"""Watched sidebar: search, sort, filters toggle and list."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QTabBar, QVBoxLayout, QWidget

from desktop.i18n import tr
from desktop.shared.detail import WatchedListItemDelegate
from desktop.shared.widgets.list_search import DebouncedLineEditSearch
from desktop.theme.scaling import control_px, layout_px, list_px
from desktop.theme.shell_layout import (
    LEFT_PANEL_TOP_COMPENSATION_PX,
    SIDEBAR_MAX_WIDTH_PX,
    SIDEBAR_MIN_WIDTH_PX,
)
from desktop.theme.layout import WATCHED_ADD_TITLE_MIN_HEIGHT
from desktop.watched.filters_panel import WatchedFiltersPanel
from desktop.watched.model import SORT_OPTIONS, WatchedEntry

WATCHED_SORT_LABEL_KEYS = {
    "user_score": "watched.sort.user_score",
    "tmdb_score": "watched.sort.tmdb_score",
    "tmdb_votes": "watched.sort.tmdb_votes",
    "tmdb_popularity": "watched.sort.tmdb_popularity",
    "year": "watched.sort.year",
    "title": "watched.sort.title",
}


def _watched_sort_label(sort_key: str, fallback: str) -> str:
    key = WATCHED_SORT_LABEL_KEYS.get(sort_key)
    return tr(key) if key is not None else fallback


def build_watched_sidebar(
    *,
    entries: list[WatchedEntry],
    on_add_title,
    on_filters_changed,
    on_selection_changed,
    on_context_menu,
    on_section_changed,
) -> tuple[QWidget, dict]:
    """Build left sidebar widgets; returns panel and named widget handles."""
    panel = QWidget()
    panel.setObjectName("watchedSidebar")
    panel.setMinimumWidth(SIDEBAR_MIN_WIDTH_PX)
    panel.setMaximumWidth(SIDEBAR_MAX_WIDTH_PX)
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, LEFT_PANEL_TOP_COMPENSATION_PX, 0, 0)
    layout.setSpacing(layout_px(14))

    section_tabs = QTabBar()
    section_tabs.setObjectName("librarySectionTabs")
    section_tabs.setExpanding(True)
    section_tabs.setDrawBase(False)
    section_tabs.addTab(tr("library.section.watched"))
    section_tabs.addTab(tr("library.section.saved"))
    section_tabs.addTab(tr("library.section.hidden"))
    section_tabs.currentChanged.connect(on_section_changed)
    layout.addWidget(section_tabs)

    add_title_button = QPushButton(tr("watched.add_title.button"))
    add_title_button.setObjectName("watchedAddTitle")
    add_title_button.setMinimumHeight(control_px(WATCHED_ADD_TITLE_MIN_HEIGHT))
    add_title_button.clicked.connect(on_add_title)
    layout.addWidget(add_title_button)

    search_input = QLineEdit()
    search_input.setObjectName("watchedSearch")
    search_input.setPlaceholderText(tr("watched.search.placeholder"))
    search_input.setClearButtonEnabled(True)
    debounced_search = DebouncedLineEditSearch(
        search_input,
        on_filters_changed,
        parent=panel,
    )
    layout.addWidget(search_input)

    sort_row = QWidget()
    sort_row.setObjectName("watchedSortRow")
    sort_layout = QHBoxLayout(sort_row)
    sort_layout.setContentsMargins(0, 0, 0, 0)
    sort_layout.setSpacing(layout_px(10))

    sort_label = QLabel(tr("common.sort"))
    sort_label.setObjectName("watchedSortLabel")

    sort_combo = QComboBox()
    sort_combo.setObjectName("watchedSort")
    for sort_key, label in SORT_OPTIONS:
        sort_combo.addItem(_watched_sort_label(sort_key, label), sort_key)
    sort_combo.currentIndexChanged.connect(on_filters_changed)

    sort_layout.addWidget(sort_label)
    sort_layout.addWidget(sort_combo, stretch=1)
    layout.addWidget(sort_row)

    filters = WatchedFiltersPanel(entries, on_filters_changed=on_filters_changed)
    layout.addWidget(filters.toggle)
    layout.addWidget(filters.panel)

    list_counter_label = QLabel("")
    list_counter_label.setObjectName("watchedListCounter")
    layout.addWidget(list_counter_label)

    list_widget = QListWidget()
    list_widget.setObjectName("watchedList")
    list_widget.setSpacing(list_px(2))
    list_widget.setUniformItemSizes(True)
    list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    list_widget.setItemDelegate(WatchedListItemDelegate(list_widget))
    list_widget.currentRowChanged.connect(on_selection_changed)
    list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    list_widget.customContextMenuRequested.connect(on_context_menu)
    layout.addWidget(list_widget, stretch=1)

    handles = {
        "section_tabs": section_tabs,
        "add_title_button": add_title_button,
        "search_input": search_input,
        "debounced_search": debounced_search,
        "sort_combo": sort_combo,
        "filters": filters,
        "list_counter_label": list_counter_label,
        "list_widget": list_widget,
    }
    return panel, handles
