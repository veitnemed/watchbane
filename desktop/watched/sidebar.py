"""Watched sidebar: search, sort, filters toggle and list."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget

from desktop.shared.detail import WatchedListItemDelegate
from desktop.shared.widgets.list_search import DebouncedLineEditSearch
from desktop.watched.filters_panel import WatchedFiltersPanel
from desktop.watched.model import SORT_OPTIONS, WatchedEntry


def build_watched_sidebar(
    *,
    entries: list[WatchedEntry],
    on_add_title,
    on_filters_changed,
    on_selection_changed,
    on_context_menu,
) -> tuple[QWidget, dict]:
    """Build left sidebar widgets; returns panel and named widget handles."""
    panel = QWidget()
    panel.setObjectName("watchedSidebar")
    panel.setMinimumWidth(300)
    panel.setMaximumWidth(400)
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)

    add_title_button = QPushButton("+ Добавить тайтл")
    add_title_button.setObjectName("watchedAddTitle")
    add_title_button.clicked.connect(on_add_title)
    layout.addWidget(add_title_button)

    search_input = QLineEdit()
    search_input.setObjectName("watchedSearch")
    search_input.setPlaceholderText("Поиск по названию")
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
    sort_layout.setSpacing(10)

    sort_label = QLabel("Сортировка")
    sort_label.setObjectName("watchedSortLabel")

    sort_combo = QComboBox()
    sort_combo.setObjectName("watchedSort")
    for sort_key, label in SORT_OPTIONS:
        sort_combo.addItem(label, sort_key)
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
    list_widget.setSpacing(2)
    list_widget.setUniformItemSizes(True)
    list_widget.setItemDelegate(WatchedListItemDelegate(list_widget))
    list_widget.currentRowChanged.connect(on_selection_changed)
    list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    list_widget.customContextMenuRequested.connect(on_context_menu)
    layout.addWidget(list_widget, stretch=1)

    handles = {
        "add_title_button": add_title_button,
        "search_input": search_input,
        "debounced_search": debounced_search,
        "sort_combo": sort_combo,
        "filters": filters,
        "list_counter_label": list_counter_label,
        "list_widget": list_widget,
    }
    return panel, handles
