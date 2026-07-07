"""Desktop Candidates tab: card list and read-only detail card."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from desktop.candidates.list_actions import CandidateListActionsMixin
from desktop.candidates.list_delegate import build_candidate_list_item_delegate
from desktop.candidates.list_model import CandidateListModel
from desktop.candidates.presenters import (
    build_candidate_readonly_detail_entry,
    build_candidate_search_index,
    candidate_detail_identity,
    candidate_sort_mode_label,
    candidate_poster_url_for_download,
)
from candidates.pool.localized_posters import ensure_candidate_localized_poster
from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS
from desktop.i18n import tr
from desktop.settings.app_settings import get_persisted_data_language
from desktop.shared.detail import DetailCard
from desktop.shared.detail import profiles as detail_profiles
from desktop.shared.widgets.list_search import DebouncedLineEditSearch, resolve_selection_row
from desktop.theme.shell_layout import (
    CANDIDATE_LIST_MAX_WIDTH_PX,
    CANDIDATE_LIST_MIN_WIDTH_PX,
    CANDIDATE_LIST_SPACING_PX,
    CANDIDATE_ROOT_MARGIN_PX,
    CANDIDATE_ROOT_SPACING_PX,
    CANDIDATE_SORT_COMBO_MAX_WIDTH_PX,
    CANDIDATE_SORT_ROW_SPACING_PX,
    CANDIDATE_SPLITTER_DETAIL_DEFAULT_PX,
    CANDIDATE_SPLITTER_LIST_DEFAULT_PX,
    DETAIL_TAB_TOP_MARGIN_PX,
    LEFT_PANEL_TOP_COMPENSATION_PX,
)
from desktop.theme.layout import CANDIDATE_LIST_MAX_WIDTH, CANDIDATE_LIST_MIN_WIDTH
from desktop.theme.scaling import list_px

logger = logging.getLogger(__name__)

CANDIDATE_LIST_STRETCH = 3
CANDIDATE_DETAIL_STRETCH = 7
CANDIDATE_LIST_ITEM_SPACING = list_px(2)


class CandidateListView(CandidateListActionsMixin):
    """Candidates tab: sort controls, card list, read-only detail card."""

    def __init__(
        self,
        session: CandidateSearchSession,
        *,
        service=None,
        on_watched_added: Callable[[object], None] | None = None,
    ) -> None:
        self._session = session
        self._service = service or session.service
        self._on_watched_added = on_watched_added
        self._data_language = get_persisted_data_language()
        self._all_candidates: list[dict] = []
        self._candidates: list[dict] = []
        self._selected_candidate: dict | None = None
        self._selected_identity: str | None = None
        self._search_index = build_candidate_search_index([])
        self._pool_unique_total = 0
        self._detail_entries: dict[str, tuple] = {}
        self._poster_request_seq = 0
        self._poster_worker = None
        self._model = CandidateListModel(parent=None, data_language=self._data_language)
        self._delegate = None

        self._widget = QWidget()
        self._widget.setObjectName("candidateListRoot")
        root_layout = QVBoxLayout(self._widget)
        root_layout.setContentsMargins(
            CANDIDATE_ROOT_MARGIN_PX,
            DETAIL_TAB_TOP_MARGIN_PX,
            CANDIDATE_ROOT_MARGIN_PX,
            CANDIDATE_ROOT_MARGIN_PX,
        )
        root_layout.setSpacing(CANDIDATE_ROOT_SPACING_PX)

        sort_label = QLabel(tr("common.sort"))
        sort_label.setObjectName("candidateSortLabel")
        self._sort_combo = QComboBox()
        self._sort_combo.setObjectName("candidateListSort")
        for mode in self._service.SEARCH_SORT_MODES:
            self._sort_combo.addItem(
                candidate_sort_mode_label(mode),
                mode,
            )
        self._sort_combo.setCurrentIndex(0)
        self._sort_combo.setMaximumWidth(CANDIDATE_SORT_COMBO_MAX_WIDTH_PX)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)

        self._counter_label = QLabel("")
        self._counter_label.setObjectName("candidateListCounter")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, stretch=1)

        list_panel = QWidget()
        list_panel.setObjectName("candidateSearchResultsPanel")
        list_panel.setMinimumWidth(CANDIDATE_LIST_MIN_WIDTH_PX)
        list_panel.setMaximumWidth(CANDIDATE_LIST_MAX_WIDTH_PX)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, LEFT_PANEL_TOP_COMPENSATION_PX, 0, 0)
        list_layout.setSpacing(CANDIDATE_LIST_SPACING_PX)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("candidateListSearch")
        self._search_input.setPlaceholderText(tr("candidates.search.placeholder"))
        self._search_input.setClearButtonEnabled(True)
        self._debounced_search = DebouncedLineEditSearch(
            self._search_input,
            self._apply_visible_candidates,
            parent=self._widget,
        )
        list_layout.addWidget(self._search_input)

        sort_row = QWidget()
        sort_row.setObjectName("candidateSortRow")
        sort_row_layout = QHBoxLayout(sort_row)
        sort_row_layout.setContentsMargins(0, 0, 0, 0)
        sort_row_layout.setSpacing(CANDIDATE_SORT_ROW_SPACING_PX)
        sort_row_layout.addWidget(sort_label)
        sort_row_layout.addWidget(self._sort_combo)
        sort_row_layout.addStretch(1)
        list_layout.addWidget(sort_row)

        self._results_list = QListView()
        self._results_list.setObjectName("candidateListWidget")
        self._results_list.setSpacing(CANDIDATE_LIST_ITEM_SPACING)
        self._results_list.setUniformItemSizes(True)
        self._results_list.setModel(self._model)
        self._delegate = build_candidate_list_item_delegate(
            self._results_list,
            session.sort_mode,
            data_language=self._data_language,
        )
        self._results_list.setItemDelegate(self._delegate)
        self._results_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._results_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        selection_model = self._results_list.selectionModel()
        if selection_model is not None:
            selection_model.currentChanged.connect(self._on_result_selected)
        list_layout.addWidget(self._results_list, stretch=1)
        list_layout.addWidget(self._counter_label)
        splitter.addWidget(list_panel)

        detail_panel = QWidget()
        detail_panel.setObjectName("candidateSearchDetailPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)

        self._detail_placeholder = QLabel(tr("candidates.detail.apply_filters_hint"))
        self._detail_placeholder.setObjectName("candidateSearchDetailPlaceholder")
        self._detail_placeholder.setWordWrap(True)
        self._detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignTop)
        detail_layout.addWidget(self._detail_placeholder)

        scroll = QScrollArea()
        scroll.setObjectName("candidateSearchDetailScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._detail_card = DetailCard(profile=detail_profiles.CANDIDATE_DETAIL_CARD_PROFILE)
        self._detail_card.set_mark_watched_handler(self._transfer_selected_to_watched)
        self._detail_card.set_hide_handler(self._hide_selected_candidate)
        scroll.setWidget(self._detail_card.widget)
        scroll.hide()
        self._detail_scroll = scroll
        detail_layout.addWidget(scroll, stretch=1)

        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, CANDIDATE_LIST_STRETCH)
        splitter.setStretchFactor(1, CANDIDATE_DETAIL_STRETCH)
        splitter.setSizes([CANDIDATE_SPLITTER_LIST_DEFAULT_PX, CANDIDATE_SPLITTER_DETAIL_DEFAULT_PX])

        session.add_listener(self.refresh)
        session.add_loading_listener(self._on_loading_changed)
        self.refresh()

    def on_tab_activated(self) -> None:
        self._refresh_data_language()
        if self._session.has_results or self._session.is_loading:
            return
        self._clear_detail(show_filters_hint=False, loading=True)
        self._session.apply_filters_async(dict(DEFAULT_BROWSE_FILTERS), parent=self._widget)

    @property
    def widget(self) -> QWidget:
        return self._widget

    def _on_sort_changed(self, _index: int) -> None:
        mode = self._sort_combo.currentData()
        if mode in self._service.SEARCH_SORT_MODES:
            self._session.set_sort_mode(str(mode))
            self._rebuild_list_delegate()

    def _rebuild_list_delegate(self) -> None:
        self._delegate = build_candidate_list_item_delegate(
            self._results_list,
            self._session.sort_mode,
            data_language=self._data_language,
        )
        self._results_list.setItemDelegate(self._delegate)
        self._results_list.viewport().update()

    def _refresh_data_language(self) -> None:
        data_language = get_persisted_data_language()
        if data_language == self._data_language:
            return
        self._data_language = data_language
        self._detail_entries = {}
        self._model.set_data_language(data_language)
        self._rebuild_list_delegate()

    def _apply_visible_candidates(self) -> None:
        query = self._search_input.text()
        previous_identity = self._selected_identity
        self._candidates = self._search_index.filter_by_query(query)

        self._results_list.blockSignals(True)
        if len(self._candidates) == 0:
            self._model.set_candidates([])
            self._selected_candidate = None
            self._selected_identity = None
            self._update_counter_label(query)
            self._clear_detail(show_filters_hint=False, search_active=bool(query.strip()))
        else:
            self._update_counter_label(query)
            self._model.set_candidates(self._candidates)
        self._results_list.blockSignals(False)

        if len(self._candidates) == 0:
            return

        row = resolve_selection_row(
            previous_identity,
            self._candidates,
            key_getter=candidate_detail_identity,
        )
        if row < 0:
            return

        selected_identity = candidate_detail_identity(self._candidates[row])
        current_row = self._results_list.currentIndex().row()
        if current_row != row:
            self._results_list.setCurrentIndex(self._model.index(row, 0))
        elif selected_identity != self._selected_identity:
            self._on_result_selected(self._model.index(row, 0), QModelIndex())

    def _update_counter_label(self, query: str) -> None:
        dup_note = ""
        if self._session.hidden_duplicates > 0:
            dup_note = tr(
                "candidates.counter.hidden_duplicates",
                count=self._session.hidden_duplicates,
            )
        visible = len(self._candidates)
        total = len(self._all_candidates)
        unique_total = self._pool_unique_total
        if query.strip():
            self._counter_label.setText(
                tr(
                    "candidates.counter.found",
                    visible=visible,
                    total=total,
                    unique_total=unique_total,
                    dup_note=dup_note,
                )
            )
        else:
            self._counter_label.setText(
                tr(
                    "candidates.counter.shown",
                    visible=visible,
                    unique_total=unique_total,
                    dup_note=dup_note,
                )
            )

    def refresh(self) -> None:
        self._refresh_data_language()
        self._poster_request_seq += 1
        if not self._session.has_results:
            self._all_candidates = []
            self._candidates = []
            self._selected_candidate = None
            self._selected_identity = None
            self._search_index = build_candidate_search_index([])
            self._pool_unique_total = 0
            self._detail_entries = {}
            self._model.set_candidates([])
            self._counter_label.setText("")
            self._clear_detail(show_filters_hint=True)
            return

        self._all_candidates = self._session.sorted_candidates()
        self._search_index = build_candidate_search_index(self._all_candidates)
        pool_stats = self._session.pool_stats()
        if not pool_stats:
            pool_stats = self._service.get_pool_stats_view()["stats"]
        self._pool_unique_total = int(
            pool_stats.get("unique_total", pool_stats.get("storage_total", 0)) or 0
        )
        self._debounced_search.flush()

    def _on_result_selected(self, current: QModelIndex, _previous: QModelIndex = QModelIndex()) -> None:
        started = perf_counter()
        row = current.row() if current.isValid() else -1
        if row < 0 or row >= len(self._candidates):
            if self._session.has_results and len(self._candidates) == 0:
                self._clear_detail(
                    show_filters_hint=False,
                    search_active=bool(self._search_input.text().strip()),
                )
            else:
                self._clear_detail(show_filters_hint=not self._session.has_results)
            return

        candidate = self._candidate_with_current_language_poster(self._candidates[row])
        self._selected_candidate = candidate
        self._selected_identity = candidate_detail_identity(candidate)
        lookup_done = perf_counter()

        identity = candidate_detail_identity(candidate)
        self._poster_request_seq += 1
        request_seq = self._poster_request_seq
        entry = self._detail_entries.get(identity)
        if entry is None:
            entry = build_candidate_readonly_detail_entry(
                candidate,
                data_language=self._data_language,
            )
            self._detail_entries[identity] = entry
        build_done = perf_counter()

        self._detail_placeholder.hide()
        self._detail_scroll.show()
        self._show_detail_entry(entry)
        render_done = perf_counter()

        poster_url = candidate_poster_url_for_download(
            candidate,
            data_language=self._data_language,
        )
        if poster_url not in (None, ""):
            self._start_poster_download(poster_url, identity, request_seq)

        total_ms = (render_done - started) * 1000
        if total_ms >= 50:
            logger.info(
                "candidate selection row=%s: lookup=%.1fms card=%.1fms render=%.1fms total=%.1fms",
                row,
                (lookup_done - started) * 1000,
                (build_done - lookup_done) * 1000,
                (render_done - build_done) * 1000,
                total_ms,
            )

    def _candidate_with_current_language_poster(self, candidate: dict) -> dict:
        try:
            updated_candidate, changed = ensure_candidate_localized_poster(
                candidate,
                data_language=self._data_language,
            )
        except Exception:
            return candidate

        if changed is not True or not isinstance(updated_candidate, dict):
            return candidate

        identity = candidate_detail_identity(candidate)
        candidate.clear()
        candidate.update(updated_candidate)
        self._detail_entries.pop(identity, None)
        self._model.update_poster_path(identity, None)
        return candidate

    def _on_loading_changed(self) -> None:
        if self._session.is_loading:
            self._counter_label.setText(tr("candidates.detail.loading"))
            self._clear_detail(show_filters_hint=False, loading=True)

    def _reset_detail_scroll(self) -> None:
        bar = self._detail_scroll.verticalScrollBar()
        bar.setValue(bar.minimum())

    def _show_detail_entry(self, entry: tuple) -> None:
        self._detail_card.show_entry(entry)
        self._reset_detail_scroll()

    def _clear_detail(
        self,
        *,
        show_filters_hint: bool,
        search_active: bool = False,
        loading: bool = False,
    ) -> None:
        self._poster_request_seq += 1
        self._detail_scroll.hide()
        self._reset_detail_scroll()
        if loading:
            self._detail_placeholder.setText(tr("candidates.detail.loading"))
            self._detail_placeholder.show()
        elif show_filters_hint:
            self._detail_placeholder.setText(tr("candidates.detail.apply_filters_hint"))
            self._detail_placeholder.show()
        elif search_active:
            self._detail_placeholder.setText(tr("candidates.detail.no_results_query"))
            self._detail_placeholder.show()
        elif self._session.has_results and len(self._candidates) == 0:
            self._detail_placeholder.setText(tr("candidates.detail.no_results"))
            self._detail_placeholder.show()
        else:
            self._detail_placeholder.setText(tr("candidates.detail.select_candidate"))
            self._detail_placeholder.show()
