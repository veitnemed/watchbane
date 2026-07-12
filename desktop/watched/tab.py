"""Desktop Watched tab: sidebar list, filters, detail card and write actions."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget

from app.use_cases.watched_library import load_watched_library as load_watched_entries
from candidates import title_state_service
from desktop.i18n import tr
from desktop.settings.app_settings import get_persisted_data_language
from desktop.shared.detail import DetailCard
from desktop.shared.widgets.list_search import resolve_selection_row
from desktop.theme.scaling import layout_px
from desktop.theme.shell_layout import (
    DETAIL_TAB_TOP_MARGIN_PX,
    LEFT_PANEL_TOP_COMPENSATION_PX,
    SPLITTER_DETAIL_DEFAULT_PX,
    SPLITTER_SIDEBAR_DEFAULT_PX,
    WATCHED_DETAIL_COLLAPSE_WIDTH_PX,
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
    prepare_card_for_display,
)
from desktop.watched.sidebar import build_watched_sidebar
from desktop.watched.library_states import (
    LIBRARY_SECTIONS,
    SECTION_HIDDEN,
    SECTION_SAVED,
    SECTION_WATCHED,
    load_action_library_entries,
)
from desktop.watched.tab_actions import WatchedTabActionsMixin

StatusCallback = Callable[[str, int], None]
EntriesCallback = Callable[[list[WatchedEntry]], None]


class _ResponsiveWatchedTab(QWidget):
    """Root widget that reports size changes to the tab view."""

    def __init__(self) -> None:
        super().__init__()
        self._resize_handler: Callable[[], None] | None = None

    def set_resize_handler(self, handler: Callable[[], None]) -> None:
        self._resize_handler = handler

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        if self._resize_handler is not None:
            self._resize_handler()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        if self._resize_handler is not None:
            self._resize_handler()


class WatchedTabView(WatchedTabActionsMixin):
    """Watched tab: list sidebar, collapsible filters, detail card, CRUD actions."""

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        on_status_message: StatusCallback | None = None,
        on_entries_changed: EntriesCallback | None = None,
        action_entries_loader=None,
        state_service=None,
    ) -> None:
        self._parent = parent
        self._on_status_message = on_status_message
        self._on_entries_changed = on_entries_changed
        self._data_language = get_persisted_data_language()
        self._action_entries_loader = action_entries_loader or load_action_library_entries
        self._state_service = state_service or title_state_service
        self._library_section = SECTION_WATCHED
        self._action_candidates_by_key: dict[str, dict] = {}

        self._watched_entries: list[WatchedEntry] = self._load_entries()
        self._entries: list[WatchedEntry] = list(self._watched_entries)
        self._watched_search_index = build_watched_search_index(self._entries)
        self._visible_entries: list[WatchedEntry] = list(self._entries)
        self._sort_key = SORT_OPTIONS[0][0]

        tab = _ResponsiveWatchedTab()
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
            on_section_changed=self._on_section_changed,
        )
        self._section_tabs = handles["section_tabs"]
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

        self._splitter = splitter
        self._left_panel = left_panel
        self._right_panel = right_panel
        self._expanded_splitter_sizes = [SPLITTER_SIDEBAR_DEFAULT_PX, SPLITTER_DETAIL_DEFAULT_PX]
        self._is_compact_layout: bool | None = None
        self._widget = tab
        tab.set_resize_handler(self._update_responsive_layout)
        self._update_responsive_layout()

        self._refresh_list()
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    @property
    def widget(self) -> QWidget:
        return self._widget

    @property
    def entries(self) -> list[WatchedEntry]:
        return self._watched_entries

    def _update_responsive_layout(self) -> None:
        compact = self._widget.width() < WATCHED_DETAIL_COLLAPSE_WIDTH_PX
        was_compact = self._is_compact_layout
        if compact == was_compact:
            return

        self._is_compact_layout = compact
        if compact:
            if was_compact is False:
                sizes = self._splitter.sizes()
                if len(sizes) == 2 and sizes[1] > 0:
                    self._expanded_splitter_sizes = sizes
            self._right_panel.hide()
            self._splitter.handle(1).hide()
            self._splitter.setSizes([max(1, self._widget.width()), 0])
            return

        self._right_panel.show()
        self._splitter.handle(1).show()
        self._splitter.setSizes(self._expanded_splitter_sizes)

    def _load_entries(self) -> list[WatchedEntry]:
        try:
            return load_watched_entries(data_language=self._data_language)
        except TypeError:
            return load_watched_entries()

    def _set_watched_entries(self, entries: list[WatchedEntry]) -> None:
        self._watched_entries = list(entries)
        if self._library_section == SECTION_WATCHED:
            self._entries = list(self._watched_entries)

    def _load_current_section_entries(self) -> None:
        self._action_candidates_by_key = {}
        if self._library_section == SECTION_WATCHED:
            self._entries = list(self._watched_entries)
        else:
            entries, candidates_by_key = self._action_entries_loader(
                self._library_section,
                data_language=self._data_language,
            )
            self._entries = list(entries)
            self._action_candidates_by_key = dict(candidates_by_key)
        self._reload_watched_search_index()

    def _on_section_changed(self, index: int) -> None:
        if index < 0 or index >= len(LIBRARY_SECTIONS):
            return
        self._library_section = LIBRARY_SECTIONS[index]
        self._load_current_section_entries()
        self._filters.reload_genre_options(self._entries)
        watched_visible = self._library_section == SECTION_WATCHED
        self._add_title_button.setVisible(watched_visible)
        self._filters.toggle.setVisible(watched_visible)
        self._filters.panel.setVisible(watched_visible and self._filters._expanded)
        self._refresh_list()
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)
        else:
            self._show_empty_details()

    def _switch_section(self, section: str, *, select_key: str | None = None) -> None:
        try:
            index = LIBRARY_SECTIONS.index(section)
        except ValueError:
            return
        if self._section_tabs.currentIndex() != index:
            self._section_tabs.setCurrentIndex(index)
        else:
            self._on_section_changed(index)
        if select_key:
            row = resolve_selection_row(
                select_key,
                self._visible_entries,
                key_getter=lambda entry: entry[0],
            )
            if row >= 0:
                self._list_widget.setCurrentRow(row)

    def reload_entries(self, added_key: str | None = None) -> None:
        """Refresh watched list after an external add (e.g. candidate transfer)."""
        self._data_language = get_persisted_data_language()
        previous_key = None
        current_row = self._list_widget.currentRow()
        if 0 <= current_row < len(self._visible_entries):
            previous_key = self._visible_entries[current_row][0]

        self._set_watched_entries(self._load_entries())
        self._load_current_section_entries()
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
            self._on_entries_changed(self._watched_entries)

    def _show_status(self, message: str, timeout_ms: int = 4000) -> None:
        if self._on_status_message is not None:
            self._on_status_message(message, timeout_ms)

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("libraryDetailPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, LEFT_PANEL_TOP_COMPENSATION_PX, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._detail_card = DetailCard()
        scroll.setWidget(self._detail_card.widget)
        self._detail_scroll = scroll
        layout.addWidget(scroll, stretch=1)

        self._state_action_panel = QFrame()
        self._state_action_panel.setObjectName("libraryStateActionPanel")
        actions_layout = QHBoxLayout(self._state_action_panel)
        actions_layout.setContentsMargins(layout_px(12), layout_px(10), layout_px(12), layout_px(10))
        actions_layout.setSpacing(layout_px(8))
        self._primary_state_action = QPushButton()
        self._primary_state_action.setObjectName("libraryPrimaryActionButton")
        self._secondary_state_action = QPushButton()
        self._secondary_state_action.setObjectName("librarySecondaryActionButton")
        self._tertiary_state_action = QPushButton()
        self._tertiary_state_action.setObjectName("libraryTertiaryActionButton")
        for button in (
            self._primary_state_action,
            self._secondary_state_action,
            self._tertiary_state_action,
        ):
            actions_layout.addWidget(button, stretch=1)
        self._primary_state_action.clicked.connect(self._run_primary_state_action)
        self._secondary_state_action.clicked.connect(self._run_secondary_state_action)
        self._tertiary_state_action.clicked.connect(self._run_tertiary_state_action)
        self._state_action_panel.hide()
        layout.addWidget(self._state_action_panel)
        return panel

    def _reset_detail_scroll(self) -> None:
        bar = self._detail_scroll.verticalScrollBar()
        bar.setValue(bar.minimum())

    def _show_detail_entry(self, entry: WatchedEntry) -> None:
        self._detail_card.show_entry(entry)
        self._reset_detail_scroll()
        if hasattr(self, "_state_action_panel"):
            self._update_state_action_panel()

    def _current_entry(self) -> WatchedEntry | None:
        row = self._list_widget.currentRow()
        if row < 0 or row >= len(self._visible_entries):
            return None
        return self._visible_entries[row]

    def _current_action_candidate(self) -> dict | None:
        entry = self._current_entry()
        if entry is None:
            return None
        return self._action_candidates_by_key.get(entry[0])

    def _configure_state_button(self, button: QPushButton, text: str | None) -> None:
        button.setVisible(bool(text))
        button.setEnabled(bool(text))
        button.setText(text or "")

    def _update_state_action_panel(self) -> None:
        if self._current_entry() is None:
            self._state_action_panel.hide()
            return
        if self._library_section == SECTION_WATCHED:
            self._configure_state_button(
                self._primary_state_action,
                tr("library.action.edit_rating"),
            )
            self._configure_state_button(
                self._secondary_state_action,
                tr("library.action.remove_watched"),
            )
            self._configure_state_button(self._tertiary_state_action, None)
        elif self._library_section == SECTION_SAVED:
            self._configure_state_button(self._primary_state_action, tr("library.action.watched"))
            self._configure_state_button(self._secondary_state_action, tr("library.action.restore"))
            self._configure_state_button(self._tertiary_state_action, tr("library.action.hide"))
        else:
            self._configure_state_button(self._primary_state_action, tr("library.action.restore"))
            self._configure_state_button(self._secondary_state_action, None)
            self._configure_state_button(self._tertiary_state_action, None)
        self._state_action_panel.show()

    def _run_primary_state_action(self) -> None:
        if self._library_section == SECTION_WATCHED:
            self._edit_user_score(self._current_entry())
        elif self._library_section == SECTION_SAVED:
            self._apply_candidate_state_action("watched")
        else:
            self._apply_candidate_state_action("restore")

    def _run_secondary_state_action(self) -> None:
        if self._library_section == SECTION_WATCHED:
            self._delete_watched_entry(self._current_entry())
        elif self._library_section == SECTION_SAVED:
            self._apply_candidate_state_action("restore")

    def _run_tertiary_state_action(self) -> None:
        if self._library_section == SECTION_SAVED:
            self._apply_candidate_state_action("hidden")

    def _apply_candidate_state_action(self, action: str) -> None:
        candidate = self._current_action_candidate()
        if candidate is None:
            return
        if action == "watched":
            result = self._state_service.mark_watched(candidate)
            self._set_watched_entries(self._load_entries())
            self._notify_entries_changed()
            self._show_status(tr("library.status.moved_watched"), 4000)
            self._switch_section(SECTION_WATCHED, select_key=result.get("dataset_key"))
            return
        if action == "hidden":
            self._state_service.hide_candidate(candidate)
            message = tr("library.status.hidden")
        else:
            self._state_service.restore_candidate(candidate)
            message = tr("library.status.restored")
        self._show_status(message, 4000)
        self._on_section_changed(self._section_tabs.currentIndex())

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
        if self._library_section == SECTION_WATCHED:
            selected_ratings = self._filters.selected_user_ratings()
            year_from, year_to = self._filters.year_filter_range()
            genre = self._filters.selected_genre()
            media_type = self._filters.selected_media_type()
            self._visible_entries = apply_view(
                self._entries,
                query,
                self._sort_key,
                None,
                None,
                year_from,
                year_to,
                genre,
                media_type,
                title_index=self._watched_search_index,
                user_ratings=selected_ratings,
            )
        else:
            self._visible_entries = apply_view(
                self._entries,
                query,
                self._sort_key,
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
        filters_available = self._library_section == SECTION_WATCHED
        score_active = filters_available and self._filters.score_filter_active()
        year_active = filters_available and self._filters.year_filter_active()
        genre_active = filters_available and self._filters.genre_filter_active()
        media_type_active = filters_available and self._filters.media_type_filter_active()
        self._list_counter_label.setText(
            format_watched_list_counter(
                visible,
                total,
                query,
                score_active,
                year_active,
                genre_active,
                media_type_active,
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
                media_type_active,
            )
        )
        self._filters.update_toggle_label()

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._visible_entries):
            self._show_empty_details()
            return
        self._show_detail_entry(self._entry_with_current_language_poster(row))

    def _entry_with_current_language_poster(self, row: int) -> WatchedEntry:
        # Selection must remain a local-only operation. Network poster refreshes
        # belong to import/maintenance flows, never the GUI selection path.
        return self._visible_entries[row]

    def _show_empty_details(self) -> None:
        if self._search_input.text().strip():
            title = tr("watched.empty.not_found")
        elif self._library_section == SECTION_SAVED:
            title = tr("library.empty.saved")
        elif self._library_section == SECTION_HIDDEN:
            title = tr("library.empty.hidden")
        else:
            title = tr("library.empty.watched")
        self._detail_card.show_empty(title)
        self._state_action_panel.hide()
        self._reset_detail_scroll()
