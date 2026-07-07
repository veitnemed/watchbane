"""Desktop Watched tab: sidebar list, filters, detail card and write actions."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QScrollArea, QSplitter, QWidget

from desktop.i18n import tr
from desktop.settings.app_settings import get_persisted_data_language
from desktop.shared.detail import DetailCard
from desktop.shared.detail.card_poster import clear_detail_poster_source_cache
from desktop.shared.detail.list_delegate import clear_list_thumb_pixmap_cache
from desktop.shared.widgets.list_search import resolve_selection_row
from desktop.theme.shell_layout import (
    DETAIL_TAB_TOP_MARGIN_PX,
    SPLITTER_DETAIL_DEFAULT_PX,
    SPLITTER_SIDEBAR_DEFAULT_PX,
    WATCHED_TAB_MARGIN_PX,
    WATCHED_TAB_SPACING_PX,
)
from desktop.watched.model import (
    SORT_OPTIONS,
    WatchedEntry,
    apply_view,
    build_watched_search_index,
    format_list_label,
    format_watched_list_counter,
    format_watched_list_status,
    load_watched_entries,
    prepare_card_for_display,
    sync_poster_for_display,
)
from desktop.watched.sidebar import build_watched_sidebar
from desktop.watched.tab_actions import WatchedTabActionsMixin

StatusCallback = Callable[[str, int], None]
EntriesCallback = Callable[[list[WatchedEntry]], None]


class WatchedTabView(WatchedTabActionsMixin):
    """Watched tab: list sidebar, collapsible filters, detail card, CRUD actions."""

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        on_status_message: StatusCallback | None = None,
        on_entries_changed: EntriesCallback | None = None,
    ) -> None:
        self._parent = parent
        self._on_status_message = on_status_message
        self._on_entries_changed = on_entries_changed
        self._data_language = get_persisted_data_language()

        self._entries: list[WatchedEntry] = self._load_entries()
        self._watched_search_index = build_watched_search_index(self._entries)
        self._visible_entries: list[WatchedEntry] = list(self._entries)
        self._sort_key = SORT_OPTIONS[0][0]

        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(
            WATCHED_TAB_MARGIN_PX,
            DETAIL_TAB_TOP_MARGIN_PX,
            WATCHED_TAB_MARGIN_PX,
            WATCHED_TAB_MARGIN_PX,
        )
        layout.setSpacing(WATCHED_TAB_SPACING_PX)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left_panel, handles = build_watched_sidebar(
            entries=self._entries,
            on_add_title=self._open_add_title_dialog,
            on_filters_changed=self._on_filters_changed,
            on_selection_changed=self._on_selection_changed,
            on_context_menu=self._open_list_context_menu,
        )
        self._add_title_button = handles["add_title_button"]
        self._search_input = handles["search_input"]
        self._debounced_search = handles["debounced_search"]
        self._sort_combo = handles["sort_combo"]
        self._filters = handles["filters"]
        self._list_counter_label = handles["list_counter_label"]
        self._list_widget = handles["list_widget"]

        right_panel = self._build_right_panel()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([SPLITTER_SIDEBAR_DEFAULT_PX, SPLITTER_DETAIL_DEFAULT_PX])

        self._widget = tab

        self._refresh_list()
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    @property
    def widget(self) -> QWidget:
        return self._widget

    @property
    def entries(self) -> list[WatchedEntry]:
        return self._entries

    def _load_entries(self) -> list[WatchedEntry]:
        try:
            return load_watched_entries(data_language=self._data_language)
        except TypeError:
            return load_watched_entries()

    def reload_entries(self, added_key: str | None = None) -> None:
        """Refresh watched list after an external add (e.g. candidate transfer)."""
        self._data_language = get_persisted_data_language()
        previous_key = None
        current_row = self._list_widget.currentRow()
        if 0 <= current_row < len(self._visible_entries):
            previous_key = self._visible_entries[current_row][0]

        self._entries = self._load_entries()
        self._reload_watched_search_index()
        self._filters.reload_genre_options(self._entries)
        self._refresh_list()
        self._notify_entries_changed()

        if self._list_widget.count() == 0:
            self._show_empty_details()
            return

        select_key = added_key or previous_key
        row_to_select = resolve_selection_row(
            select_key,
            self._visible_entries,
            key_getter=lambda entry: entry[0],
        )
        if row_to_select < 0:
            self._show_empty_details()
            return

        self._list_widget.blockSignals(True)
        self._list_widget.setCurrentRow(row_to_select)
        self._list_widget.blockSignals(False)
        self._show_detail_entry(self._entry_with_current_language_poster(row_to_select))

    def _notify_entries_changed(self) -> None:
        if self._on_entries_changed is not None:
            self._on_entries_changed(self._entries)

    def _show_status(self, message: str, timeout_ms: int = 4000) -> None:
        if self._on_status_message is not None:
            self._on_status_message(message, timeout_ms)

    def _build_right_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._detail_card = DetailCard()
        scroll.setWidget(self._detail_card.widget)
        self._detail_scroll = scroll
        return scroll

    def _reset_detail_scroll(self) -> None:
        bar = self._detail_scroll.verticalScrollBar()
        bar.setValue(bar.minimum())

    def _show_detail_entry(self, entry: WatchedEntry) -> None:
        self._detail_card.show_entry(entry)
        self._reset_detail_scroll()

    def _reload_watched_search_index(self) -> None:
        self._watched_search_index = build_watched_search_index(self._entries)

    def _current_entry_key(self) -> str | None:
        row = self._list_widget.currentRow()
        if row < 0 or row >= len(self._visible_entries):
            return None
        return self._visible_entries[row][0]

    def _on_filters_changed(self) -> None:
        self._sort_key = self._sort_combo.currentData()
        previous_key = self._current_entry_key()
        self._refresh_list()

        row_to_select = resolve_selection_row(
            previous_key,
            self._visible_entries,
            key_getter=lambda entry: entry[0],
        )
        if row_to_select >= 0:
            self._list_widget.setCurrentRow(row_to_select)

    def _refresh_list(self) -> None:
        from PyQt6.QtWidgets import QListWidgetItem

        query = self._search_input.text()
        min_score, max_score = self._filters.score_filter_range()
        year_from, year_to = self._filters.year_filter_range()
        genre = self._filters.selected_genre()
        self._visible_entries = apply_view(
            self._entries,
            query,
            self._sort_key,
            min_score,
            max_score,
            year_from,
            year_to,
            genre,
            title_index=self._watched_search_index,
        )

        self._list_widget.blockSignals(True)
        self._list_widget.clear()
        for entry in self._visible_entries:
            _, _, card = entry
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(format_list_label(card))
            self._list_widget.addItem(item)
        self._list_widget.blockSignals(False)

        if self._list_widget.count() == 0:
            self._show_empty_details()
        self._update_list_status()

    def _update_list_status(self) -> None:
        visible = len(self._visible_entries)
        total = len(self._entries)
        query = self._search_input.text()
        score_active = self._filters.score_filter_active()
        year_active = self._filters.year_filter_active()
        genre_active = self._filters.genre_filter_active()
        self._list_counter_label.setText(
            format_watched_list_counter(
                visible,
                total,
                query,
                score_active,
                year_active,
                genre_active,
            )
        )
        self._show_status(
            format_watched_list_status(
                visible,
                total,
                query,
                score_active,
                year_active,
                genre_active,
            )
        )
        self._filters.update_toggle_label()

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._visible_entries):
            self._show_empty_details()
            return
        self._show_detail_entry(self._entry_with_current_language_poster(row))

    def _entry_with_current_language_poster(self, row: int) -> WatchedEntry:
        entry = self._visible_entries[row]
        key, movie, _card = entry
        try:
            result = sync_poster_for_display(movie, data_language=self._data_language)
        except Exception:
            return entry

        if result.get("updated") is not True:
            return entry

        self._clear_replaced_poster_pixmap_cache(result)
        updated_entry = (
            key,
            movie,
            prepare_card_for_display(movie, data_language=self._data_language),
        )
        self._visible_entries[row] = updated_entry
        self._update_list_item_entry(row, updated_entry)
        for index, existing in enumerate(self._entries):
            if existing[0] == key:
                self._entries[index] = updated_entry
                break
        return updated_entry

    def _update_list_item_entry(self, row: int, entry: WatchedEntry) -> None:
        if row < 0 or row >= self._list_widget.count():
            return
        item = self._list_widget.item(row)
        if item is None:
            return
        item.setData(Qt.ItemDataRole.UserRole, entry)
        item.setToolTip(format_list_label(entry[2]))
        self._list_widget.viewport().update()

    def _clear_replaced_poster_pixmap_cache(self, result: dict) -> None:
        paths = []
        download = result.get("download")
        if isinstance(download, dict):
            paths.append(download.get("local_path"))
        entry = result.get("entry")
        if isinstance(entry, dict):
            paths.append(entry.get("local_path"))

        for path in paths:
            if path in (None, ""):
                continue
            clear_detail_poster_source_cache(str(path))
            clear_list_thumb_pixmap_cache(str(path))

    def _show_empty_details(self) -> None:
        if self._search_input.text().strip():
            title = tr("watched.empty.not_found")
        else:
            title = tr("watched.empty.select_title")
        self._detail_card.show_empty(title)
        self._reset_detail_scroll()
