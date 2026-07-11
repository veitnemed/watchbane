"""Write actions and context menu handlers for the Watched tab."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QMenu

from desktop.i18n import tr
from desktop.shared.widgets.list_search import resolve_selection_row
from desktop.watched.delete import (
    execute_watched_delete,
    format_delete_status_message,
    load_delete_preview,
)
from desktop.watched.dialogs.delete_dialog import WatchedDeleteDialog
from desktop.watched.dialogs.score_edit import ScoreEditDialog
from desktop.watched.model import (
    WatchedEntry,
    format_save_user_score_status,
    load_watched_entries,
    save_watched_user_score,
    validate_score_edit_entry,
)


class WatchedTabActionsMixin:
    """CRUD and add-title actions for WatchedTabView."""

    def _load_entries_for_actions(self):
        loader = getattr(self, "_load_entries", None)
        if callable(loader):
            return loader()
        return load_watched_entries()

    def _open_add_title_dialog(self) -> None:
        from desktop.watched.add_title import run_add_title_flow

        result = run_add_title_flow(self._parent)
        if result is None or result.ok is False:
            return

        added_key = result.title
        self.reload_entries(added_key=added_key)
        self._show_status(result.message or tr("watched.status.new_entry_added"), 5000)

    def _open_list_context_menu(self, position) -> None:
        if getattr(self, "_library_section", "watched") != "watched":
            return
        item = self._list_widget.itemAt(position)
        entry = self._entry_from_item(item)
        is_valid, _message = validate_score_edit_entry(entry)
        if is_valid is False:
            return

        self._list_widget.setCurrentItem(item)
        menu = QMenu(self._list_widget)
        edit_action = menu.addAction(tr("watched.context.edit_score"))
        delete_action = menu.addAction(tr("watched.context.delete_record"))
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
            self._show_status(tr("watched.record.not_found"), 4000)
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
        loaded_entries = self._load_entries_for_actions()
        setter = getattr(self, "_set_watched_entries", None)
        if callable(setter):
            setter(loaded_entries)
        else:
            self._entries = loaded_entries
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
            self._show_detail_entry(self._visible_entries[row_to_select])
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

    def _refresh_after_user_score_save(self, current_key: str, result) -> None:
        loaded_entries = self._load_entries_for_actions()
        setter = getattr(self, "_set_watched_entries", None)
        if callable(setter):
            setter(loaded_entries)
        else:
            self._entries = loaded_entries
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
            self._show_detail_entry(self._visible_entries[row_to_select])

        self._show_status(format_save_user_score_status(result), 4000)

    def _entry_from_item(self, item) -> WatchedEntry | None:
        if item is None:
            return None
        entry = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(entry, tuple) and len(entry) == 3:
            return entry
        return None
