"""Desktop Candidates tab: card list and read-only detail card."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from candidates import service as candidate_service
from desktop.candidates.list_delegate import build_candidate_list_item_delegate
from desktop.candidates.presenters import (
    build_candidate_readonly_detail_entry,
    build_candidate_search_index,
    candidate_detail_identity,
    candidate_poster_url_for_download,
)
from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS
from desktop.candidates.workers.poster_worker import CandidatePosterDownloadWorker
from desktop.shared.widgets.list_search import DebouncedLineEditSearch, resolve_selection_row
from desktop.shared.detail import (
    CANDIDATE_DETAIL_CARD_PROFILE,
    WatchedDetailCard,
)

logger = logging.getLogger(__name__)

CANDIDATE_LIST_MIN_WIDTH = 280
CANDIDATE_LIST_MAX_WIDTH = 380
CANDIDATE_LIST_STRETCH = 3
CANDIDATE_DETAIL_STRETCH = 7


class CandidateListView:
    """Candidates tab: sort controls, card list, read-only detail card."""

    def __init__(
        self,
        session: CandidateSearchSession,
        *,
        on_watched_added: Callable[[object], None] | None = None,
    ) -> None:
        self._session = session
        self._on_watched_added = on_watched_added
        self._all_candidates: list[dict] = []
        self._candidates: list[dict] = []
        self._selected_candidate: dict | None = None
        self._selected_identity: str | None = None
        self._search_index = build_candidate_search_index([])
        self._pool_unique_total = 0
        self._detail_entries: dict[str, tuple] = {}
        self._poster_request_seq = 0
        self._poster_worker: CandidatePosterDownloadWorker | None = None
        self._delegate = build_candidate_list_item_delegate(None, session.sort_mode)

        self._widget = QWidget()
        self._widget.setObjectName("candidateListRoot")
        root_layout = QVBoxLayout(self._widget)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        sort_label = QLabel("Сортировка")
        sort_label.setObjectName("candidateSortLabel")
        self._sort_combo = QComboBox()
        self._sort_combo.setObjectName("candidateListSort")
        for mode in candidate_service.SEARCH_SORT_MODES:
            self._sort_combo.addItem(
                candidate_service.SEARCH_SORT_MODE_LABELS[mode],
                mode,
            )
        self._sort_combo.setCurrentIndex(0)
        self._sort_combo.setMaximumWidth(160)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)

        self._counter_label = QLabel("")
        self._counter_label.setObjectName("candidateListCounter")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, stretch=1)

        list_panel = QWidget()
        list_panel.setObjectName("candidateSearchResultsPanel")
        list_panel.setMinimumWidth(CANDIDATE_LIST_MIN_WIDTH)
        list_panel.setMaximumWidth(CANDIDATE_LIST_MAX_WIDTH)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(14)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("candidateListSearch")
        self._search_input.setPlaceholderText("Поиск по названию")
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
        sort_row_layout.setSpacing(10)
        sort_row_layout.addWidget(sort_label)
        sort_row_layout.addWidget(self._sort_combo)
        sort_row_layout.addStretch(1)
        list_layout.addWidget(sort_row)

        self._results_list = QListWidget()
        self._results_list.setObjectName("candidateListWidget")
        self._results_list.setSpacing(2)
        self._results_list.setUniformItemSizes(True)
        self._results_list.setItemDelegate(self._delegate)
        self._results_list.currentRowChanged.connect(self._on_result_selected)
        list_layout.addWidget(self._results_list, stretch=1)
        list_layout.addWidget(self._counter_label)
        splitter.addWidget(list_panel)

        detail_panel = QWidget()
        detail_panel.setObjectName("candidateSearchDetailPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)

        self._detail_placeholder = QLabel("Сначала примените фильтры на вкладке «Фильтры»")
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

        self._detail_card = WatchedDetailCard(profile=CANDIDATE_DETAIL_CARD_PROFILE)
        self._detail_card.set_mark_watched_handler(self._transfer_selected_to_watched)
        scroll.setWidget(self._detail_card.widget)
        scroll.hide()
        self._detail_scroll = scroll
        detail_layout.addWidget(scroll, stretch=1)

        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, CANDIDATE_LIST_STRETCH)
        splitter.setStretchFactor(1, CANDIDATE_DETAIL_STRETCH)
        splitter.setSizes([CANDIDATE_LIST_MAX_WIDTH, 800])

        session.add_listener(self.refresh)
        self.refresh()

    def on_tab_activated(self) -> None:
        if self._session.has_results:
            return
        self._session.apply_filters(dict(DEFAULT_BROWSE_FILTERS))

    def _transfer_selected_to_watched(self) -> None:
        candidate = self._selected_candidate
        if not isinstance(candidate, dict):
            return

        from desktop.watched.add_title import run_candidate_transfer_flow

        parent = self._widget.window()
        result = run_candidate_transfer_flow(parent, candidate)
        if result is None or getattr(result, "ok", False) is False:
            return

        self._selected_candidate = None
        if self._session.filters is not None:
            self._session.apply_filters(self._session.filters)
        if self._on_watched_added is not None:
            self._on_watched_added(result)

    @property
    def widget(self) -> QWidget:
        return self._widget

    def _on_sort_changed(self, _index: int) -> None:
        mode = self._sort_combo.currentData()
        if mode in candidate_service.SEARCH_SORT_MODES:
            self._session.set_sort_mode(str(mode))
            self._delegate = build_candidate_list_item_delegate(self._results_list, self._session.sort_mode)
            self._results_list.setItemDelegate(self._delegate)
            self._results_list.viewport().update()

    def _apply_visible_candidates(self) -> None:
        query = self._search_input.text()
        previous_identity = self._selected_identity
        self._candidates = self._search_index.filter_by_query(query)

        self._results_list.blockSignals(True)
        self._results_list.clear()
        if len(self._candidates) == 0:
            self._selected_candidate = None
            self._selected_identity = None
            self._update_counter_label(query)
            self._clear_detail(show_filters_hint=False, search_active=bool(query.strip()))
        else:
            self._update_counter_label(query)
            for candidate in self._candidates:
                from PyQt6.QtWidgets import QListWidgetItem

                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, candidate)
                self._results_list.addItem(item)
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
        current_row = self._results_list.currentRow()
        if current_row != row:
            self._results_list.setCurrentRow(row)
        elif selected_identity != self._selected_identity:
            self._on_result_selected(row)

    def _update_counter_label(self, query: str) -> None:
        dup_note = ""
        if self._session.hidden_duplicates > 0:
            dup_note = f" · дублей скрыто: {self._session.hidden_duplicates}"
        visible = len(self._candidates)
        total = len(self._all_candidates)
        unique_total = self._pool_unique_total
        if query.strip():
            self._counter_label.setText(
                f"Найдено {visible} из {total} · уникальных в pool: {unique_total}{dup_note}"
            )
        else:
            self._counter_label.setText(
                f"Показано {visible} · уникальных в pool: {unique_total}{dup_note}"
            )

    def refresh(self) -> None:
        self._poster_request_seq += 1
        if not self._session.has_results:
            self._all_candidates = []
            self._candidates = []
            self._selected_candidate = None
            self._selected_identity = None
            self._search_index = build_candidate_search_index([])
            self._pool_unique_total = 0
            self._detail_entries = {}
            self._results_list.clear()
            self._counter_label.setText("")
            self._clear_detail(show_filters_hint=True)
            return

        self._all_candidates = self._session.sorted_candidates()
        self._search_index = build_candidate_search_index(self._all_candidates)
        pool_stats = candidate_service.get_pool_stats_view()["stats"]
        self._pool_unique_total = int(
            pool_stats.get("unique_total", pool_stats.get("storage_total", 0)) or 0
        )
        self._debounced_search.flush()

    def _on_result_selected(self, row: int) -> None:
        started = perf_counter()
        if row < 0 or row >= len(self._candidates):
            if self._session.has_results and len(self._candidates) == 0:
                self._clear_detail(
                    show_filters_hint=False,
                    search_active=bool(self._search_input.text().strip()),
                )
            else:
                self._clear_detail(show_filters_hint=not self._session.has_results)
            return

        candidate = self._candidates[row]
        self._selected_candidate = candidate
        self._selected_identity = candidate_detail_identity(candidate)
        lookup_done = perf_counter()

        identity = candidate_detail_identity(candidate)
        self._poster_request_seq += 1
        request_seq = self._poster_request_seq
        entry = self._detail_entries.get(identity)
        if entry is None:
            entry = build_candidate_readonly_detail_entry(candidate)
            self._detail_entries[identity] = entry
        build_done = perf_counter()

        self._detail_placeholder.hide()
        self._detail_scroll.show()
        self._detail_card.show_entry(entry)
        render_done = perf_counter()

        poster_url = candidate_poster_url_for_download(candidate)
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

    def _start_poster_download(self, poster_url: str, identity: str, request_seq: int) -> None:
        worker = CandidatePosterDownloadWorker(poster_url, parent=self._widget)
        worker.finished_with_path.connect(
            lambda local_path, seq=request_seq, ident=identity: self._on_poster_download_finished(
                seq,
                ident,
                local_path,
            )
        )
        worker.finished.connect(worker.deleteLater)
        self._poster_worker = worker
        worker.start()

    def _on_poster_download_finished(self, request_seq: int, identity: str, local_path: str) -> None:
        if request_seq != self._poster_request_seq:
            return

        entry = self._detail_entries.get(identity)
        if entry is not None:
            entry_key, movie, card = entry
            updated_card = dict(card)
            updated_card["poster_path"] = local_path
            updated_card["poster_src"] = local_path
            self._detail_entries[identity] = (entry_key, movie, updated_card)

        self._detail_card.apply_local_poster_path(local_path)
        self._results_list.viewport().update()

    def _clear_detail(self, *, show_filters_hint: bool, search_active: bool = False) -> None:
        self._poster_request_seq += 1
        self._detail_scroll.hide()
        if show_filters_hint:
            self._detail_placeholder.setText("Сначала примените фильтры на вкладке «Фильтры»")
            self._detail_placeholder.show()
        elif search_active:
            self._detail_placeholder.setText("Ничего не найдено по запросу.")
            self._detail_placeholder.show()
        elif self._session.has_results and len(self._candidates) == 0:
            self._detail_placeholder.setText("Нет кандидатов после фильтра.")
            self._detail_placeholder.show()
        else:
            self._detail_placeholder.setText("Выберите кандидата из списка")
            self._detail_placeholder.show()
