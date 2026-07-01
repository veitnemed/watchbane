"""Desktop Watched tab: sidebar list, filters, detail card and write actions."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QMenu, QScrollArea, QSplitter, QWidget

from desktop.shared.detail import WatchedDetailCard
from desktop.shared.widgets.list_search import resolve_selection_row
from desktop.watched.delete import (
    execute_watched_delete,
    format_delete_status_message,
    load_delete_preview,
)
from desktop.watched.dialogs.delete_dialog import WatchedDeleteDialog
from desktop.watched.dialogs.score_edit import ScoreEditDialog
from desktop.watched.model import (
    SORT_OPTIONS,
    WatchedEntry,
    apply_view,
    build_watched_search_index,
    format_list_label,
    format_save_user_score_status,
    format_watched_list_counter,
    format_watched_list_status,
    load_watched_entries,
    save_watched_user_score,
    validate_score_edit_entry,
)
from desktop.watched.sidebar import build_watched_sidebar

StatusCallback = Callable[[str, int], None]
EntriesCallback = Callable[[list[WatchedEntry]], None]


class WatchedTabView:
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

        self._entries: list[WatchedEntry] = load_watched_entries()
        self._watched_search_index = build_watched_search_index(self._entries)
        self._visible_entries: list[WatchedEntry] = list(self._entries)
        self._sort_key = SORT_OPTIONS[0][0]

        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

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
        self._sort_combo = handles["sort_combo"]
        self._filters = handles["filters"]
        self._list_counter_label = handles["list_counter_label"]
        self._list_widget = handles["list_widget"]

        right_panel = self._build_right_panel()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 840])

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

    def reload_entries(self, added_key: str | None = None) -> None:
        """Refresh watched list after an external add (e.g. candidate transfer)."""
        previous_key = None
        current_row = self._list_widget.currentRow()
        if 0 <= current_row < len(self._visible_entries):
            previous_key = self._visible_entries[current_row][0]

        self._entries = load_watched_entries()
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
        self._detail_card.show_entry(self._visible_entries[row_to_select])

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

        self._detail_card = WatchedDetailCard()
        scroll.setWidget(self._detail_card.widget)
        return scroll

    def _open_add_title_dialog(self) -> None:
        from desktop.watched.add_title import run_add_title_flow

        result = run_add_title_flow(self._parent)
        if result is None or result.ok is False:
            return

        added_key = result.title
        self.reload_entries(added_key=added_key)
        self._show_status(result.message or "Новая запись добавлена!", 5000)

    def _reload_watched_search_index(self) -> None:
        self._watched_search_index = build_watched_search_index(self._entries)

    def _current_entry_key(self) -> str | None:
        row = self._list_widget.currentRow()
        if row < 0 or row >= len(self._visible_entries):
            return None
        return self._visible_entries[row][0]

    def _refresh_after_user_score_save(self, current_key: str, result) -> None:
        self._entries = load_watched_entries()
        self._reload_watched_search_index()
        self._refresh_list()
        self._notify_entries_changed()

        row_to_select = resolve_selection_row(
            current_key,
            self._visible_entries,
            key_getter=lambda entry: entry[0],
        )
        if row_to_select >= 0:
            self._list_widget.blockSignals(True)
            self._list_widget.setCurrentRow(row_to_select)
            self._list_widget.blockSignals(False)
            self._detail_card.show_entry(self._visible_entries[row_to_select])

        self._show_status(format_save_user_score_status(result), 4000)

    def _entry_from_item(self, item) -> WatchedEntry | None:
        if item is None:
            return None
        entry = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(entry, tuple) and len(entry) == 3:
            return entry
        return None

    def _open_list_context_menu(self, position) -> None:
        item = self._list_widget.itemAt(position)
        entry = self._entry_from_item(item)
        is_valid, _message = validate_score_edit_entry(entry)
        if is_valid is False:
            return

        self._list_widget.setCurrentItem(item)
        menu = QMenu(self._list_widget)
        edit_action = menu.addAction("Изменить оценку")
        delete_action = menu.addAction("Удалить запись")
        chosen_action = menu.exec(self._list_widget.viewport().mapToGlobal(position))
        if chosen_action is edit_action:
            self._edit_user_score(entry)
        elif chosen_action is delete_action:
            self._delete_watched_entry(entry)

    def _delete_watched_entry(self, entry: WatchedEntry | None) -> None:
        is_valid, message = validate_score_edit_entry(entry)
        if is_valid is False:
            self._show_status(message, 4000)
            return

        dataset_key, _movie, _card = entry
        preview = load_delete_preview(dataset_key)
        if preview is None:
            self._show_status("Запись не найдена", 4000)
            return

        dialog = WatchedDeleteDialog(preview, parent=self._parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        result = execute_watched_delete(dataset_key)
        if result.get("ok"):
            self._refresh_after_delete(result)
            return

        self._show_status(format_delete_status_message(result), 4000)

    def _refresh_after_delete(self, result: dict) -> None:
        previous_key = self._current_entry_key()
        self._entries = load_watched_entries()
        self._reload_watched_search_index()
        self._filters.reload_genre_options(self._entries)
        self._refresh_list()
        self._notify_entries_changed()

        if self._list_widget.count() > 0:
            row_to_select = resolve_selection_row(
                previous_key,
                self._visible_entries,
                key_getter=lambda entry: entry[0],
            )
            if row_to_select < 0:
                row_to_select = 0
            self._list_widget.blockSignals(True)
            self._list_widget.setCurrentRow(row_to_select)
            self._list_widget.blockSignals(False)
            self._detail_card.show_entry(self._visible_entries[row_to_select])
        else:
            self._show_empty_details()

        self._show_status(format_delete_status_message(result), 4000)

    def _edit_user_score(self, entry: WatchedEntry | None) -> None:
        is_valid, message = validate_score_edit_entry(entry)
        if is_valid is False:
            self._show_status(message, 4000)
            return

        score = self._show_user_score_dialog(entry)
        if score is None:
            return

        dataset_key, _movie, _card = entry
        result = save_watched_user_score(dataset_key, score)
        if result.ok and result.reason in ("updated", "nothing_changed"):
            self._refresh_after_user_score_save(dataset_key, result)
            return

        self._show_status(format_save_user_score_status(result), 4000)

    def _show_user_score_dialog(self, entry: WatchedEntry) -> float | None:
        dialog = ScoreEditDialog(entry, parent=self._parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.score_value()

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
        self._detail_card.show_entry(self._visible_entries[row])

    def _show_empty_details(self) -> None:
        if self._search_input.text().strip():
            title = "Ничего не найдено"
        else:
            title = "Выберите тайтл слева"
        self._detail_card.show_empty(title)
