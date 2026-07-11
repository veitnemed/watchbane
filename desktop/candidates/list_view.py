"""Desktop Candidates tab: card list and read-only detail card."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from time import perf_counter

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from candidates.pool.localized_posters import candidate_needs_tmdb_detail_enrichment
from candidates.recommendation_deck_service import RecommendationDeckService
from candidates.scoring.rating_confidence import has_unknown_rating
from desktop.candidates.list_actions import CandidateListActionsMixin
from desktop.candidates.list_delegate import build_candidate_list_item_delegate
from desktop.candidates.list_model import CandidateListModel
from desktop.candidates.presenters import (
    build_candidate_readonly_detail_entry,
    build_candidate_search_index,
    candidate_detail_identity,
    candidate_poster_url_for_download,
)
from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS
from desktop.candidates.workers.poster_worker import CandidateLocalizedPosterWorker
from desktop.i18n import get_interface_language, tr
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
    CANDIDATE_SPLITTER_DETAIL_DEFAULT_PX,
    CANDIDATE_SPLITTER_LIST_DEFAULT_PX,
    DETAIL_TAB_TOP_MARGIN_PX,
    LEFT_PANEL_TOP_COMPENSATION_PX,
)
from desktop.theme.layout import CANDIDATE_LIST_MAX_WIDTH, CANDIDATE_LIST_MIN_WIDTH
from desktop.theme.scaling import list_px

logger = logging.getLogger(__name__)

CANDIDATE_LIST_STRETCH = 0
CANDIDATE_DETAIL_STRETCH = 1
CANDIDATE_LIST_ITEM_SPACING = list_px(2)


class CandidateListView(CandidateListActionsMixin):
    """Recommendations tab backed by a bounded, refillable candidate deck."""

    def __init__(
        self,
        session: CandidateSearchSession,
        *,
        service=None,
        deck_service: RecommendationDeckService | None = None,
        on_watched_added: Callable[[object], None] | None = None,
    ) -> None:
        self._session = session
        self._service = service or session.service
        self._deck_service = deck_service or RecommendationDeckService(
            pool_loader=self._load_pool_for_deck,
        )
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
        self._localized_poster_workers: list[CandidateLocalizedPosterWorker] = []
        self._localized_poster_inflight: set[str] = set()
        self._model = CandidateListModel(parent=None, data_language=self._data_language)
        self._delegate = None
        self._last_logged_search_signature: tuple | None = None
        self._deck: dict | None = None
        self._recommendations_active = False
        self._deck_dirty = True

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

        self._counter_label = QLabel("", self._widget)
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

        self._search_input = QLineEdit(list_panel)
        self._search_input.setObjectName("candidateListSearch")
        self._search_input.setPlaceholderText(tr("candidates.search.placeholder"))
        self._search_input.setClearButtonEnabled(True)
        self._debounced_search = DebouncedLineEditSearch(
            self._search_input,
            self._on_search_query_changed,
            parent=self._widget,
        )
        self._search_input.hide()

        self._deck_status_label = QLabel("")
        self._deck_status_label.setObjectName("recommendationsDeckStatus")
        self._deck_status_label.setWordWrap(True)
        self._deck_status_label.hide()

        feed_header = QWidget()
        feed_header.setObjectName("recommendationsFeedHeader")
        feed_header_layout = QHBoxLayout(feed_header)
        feed_header_layout.setContentsMargins(0, 0, 0, 0)
        feed_header_layout.setSpacing(list_px(10))
        self._feed_title = QLabel(tr("recommendations.feed.title"))
        self._feed_title.setObjectName("recommendationsFeedTitle")
        feed_header_layout.addWidget(self._feed_title)
        feed_header_layout.addStretch(1)
        feed_header_layout.addWidget(self._deck_status_label)
        self._new_deck_button = QPushButton(tr("recommendations.new_deck"))
        self._new_deck_button.setObjectName("recommendationsNewDeckButton")
        self._new_deck_button.clicked.connect(self._on_new_deck_clicked)
        self._new_deck_button.hide()
        list_layout.addWidget(feed_header)

        self._results_list = QListView()
        self._results_list.setObjectName("candidateListWidget")
        self._results_list.setSpacing(CANDIDATE_LIST_ITEM_SPACING)
        self._results_list.setUniformItemSizes(True)
        self._results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        self._counter_label.hide()
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
        scroll.setWidget(self._detail_card.widget)
        scroll.hide()
        self._detail_scroll = scroll
        detail_layout.addWidget(scroll, stretch=1)

        self._action_panel = QFrame()
        self._action_panel.setObjectName("recommendationActionPanel")
        action_layout = QVBoxLayout(self._action_panel)
        action_layout.setContentsMargins(
            0,
            list_px(12),
            0,
            0,
        )
        action_layout.setSpacing(list_px(8))
        self._reason_title = QLabel(tr("recommendations.reasons.title"))
        self._reason_title.setObjectName("recommendationReasonsTitle")
        action_layout.addWidget(self._reason_title)
        self._reason_label = QLabel("")
        self._reason_label.setObjectName("recommendationReasonsText")
        self._reason_label.setWordWrap(True)
        action_layout.addWidget(self._reason_label)

        action_buttons_layout = QGridLayout()
        action_buttons_layout.setContentsMargins(0, 0, 0, 0)
        action_buttons_layout.setHorizontalSpacing(list_px(8))
        action_buttons_layout.setVerticalSpacing(list_px(6))
        self._watched_action_button = QPushButton(tr("recommendations.action.watched"))
        self._watched_action_button.setObjectName("recommendationWatchedButton")
        self._watchlist_action_button = QPushButton(tr("recommendations.action.watchlist"))
        self._watchlist_action_button.setObjectName("recommendationWatchlistButton")
        self._hidden_action_button = QPushButton(tr("recommendations.action.hidden"))
        self._hidden_action_button.setObjectName("recommendationHiddenButton")
        self._watched_action_button.clicked.connect(
            lambda: self._apply_recommendation_action("watched")
        )
        self._watchlist_action_button.clicked.connect(
            lambda: self._apply_recommendation_action("watchlist")
        )
        self._hidden_action_button.clicked.connect(
            lambda: self._apply_recommendation_action("hidden")
        )
        action_buttons = (
            self._watched_action_button,
            self._watchlist_action_button,
            self._hidden_action_button,
        )
        for column, button in enumerate(action_buttons):
            action_buttons_layout.addWidget(button, 0, column)
            action_buttons_layout.setColumnStretch(column, 1)
        action_layout.addLayout(action_buttons_layout)
        self._detail_card.add_main_info_footer(self._action_panel)
        self._set_action_panel_enabled(False)

        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, CANDIDATE_LIST_STRETCH)
        splitter.setStretchFactor(1, CANDIDATE_DETAIL_STRETCH)
        splitter.setSizes([CANDIDATE_SPLITTER_LIST_DEFAULT_PX, CANDIDATE_SPLITTER_DETAIL_DEFAULT_PX])

        session.add_listener(self.refresh)
        session.add_loading_listener(self._on_loading_changed)
        self._clear_detail(show_filters_hint=True)

    def on_tab_activated(self) -> None:
        self._refresh_data_language()
        self._recommendations_active = True
        self._load_recommendation_deck(force_new=False)

    @property
    def widget(self) -> QWidget:
        return self._widget

    def _load_pool_for_deck(self) -> dict:
        view = self._service.get_search_overview_view()
        candidates = (view.get("candidates") or []) if isinstance(view, dict) else []
        return {
            candidate_detail_identity(candidate): candidate
            for candidate in candidates
            if isinstance(candidate, dict)
        }

    def _deck_preferences(self) -> dict:
        return dict(self._session.filters or DEFAULT_BROWSE_FILTERS)

    def _set_action_panel_enabled(self, enabled: bool) -> None:
        self._action_panel.setVisible(enabled)
        for button in (
            self._watched_action_button,
            self._watchlist_action_button,
            self._hidden_action_button,
        ):
            button.setEnabled(enabled)
        if not enabled:
            self._reason_label.clear()

    def _country_reason_value(self, candidate: dict) -> str:
        from candidates.models.country_reference import (
            COUNTRY_NAME_BY_ISO2,
            ENGLISH_COUNTRY_NAME_BY_ISO2,
            country_value_to_iso2,
        )

        value = candidate.get("country") or candidate.get("origin_country") or ""
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        text = str(value or "").strip()
        iso2 = country_value_to_iso2(text) or text.upper()
        names = ENGLISH_COUNTRY_NAME_BY_ISO2 if get_interface_language() == "en" else COUNTRY_NAME_BY_ISO2
        return names.get(iso2, text)

    def _recommendation_reasons(self, candidate: dict) -> list[str]:
        reasons: list[str] = []
        country = self._country_reason_value(candidate)
        try:
            year = int(candidate.get("year"))
        except (TypeError, ValueError):
            year = None
        if year is not None and year >= datetime.now().year - 2:
            if country:
                reasons.append(tr("recommendations.reason.recent_country", country=country))
            else:
                reasons.append(tr("recommendations.reason.recent"))
            if has_unknown_rating(candidate):
                reasons.append(tr("recommendations.reason.unrated_new"))
        preferences = self._deck_preferences()
        vibe = (
            preferences.get("vibe")
            or preferences.get("tone")
            or preferences.get("atmosphere")
        )
        if vibe not in (None, "", "any", "mixed"):
            reasons.append(tr("recommendations.reason.vibe", vibe=vibe))
        try:
            tmdb_score = float(candidate.get("tmdb_score"))
        except (TypeError, ValueError):
            tmdb_score = 0.0
        if not has_unknown_rating(candidate) and tmdb_score >= 7.5:
            reasons.append(tr("recommendations.reason.tmdb_interest"))
        if not reasons:
            reasons.append(tr("recommendations.reason.preferences"))
        return reasons[:3]

    def _update_recommendation_reasons(self, candidate: dict) -> None:
        self._reason_label.setText("\n".join(f"• {reason}" for reason in self._recommendation_reasons(candidate)))

    def _update_deck_status(self) -> None:
        deck = self._deck or {}
        active_count = len(deck.get("active") or [])
        if active_count == 0:
            excluded = deck.get("excluded") if isinstance(deck.get("excluded"), dict) else {}
            processed_count = int(excluded.get("watched") or 0) + int(excluded.get("actioned") or 0)
            pool_total = int(excluded.get("pool_total") or 0)
            if deck.get("last_action") or (pool_total > 0 and processed_count >= pool_total):
                text = tr("recommendations.state.processed")
            else:
                text = tr("recommendations.state.empty")
        elif self._session.last_error:
            text = tr("recommendations.state.local_available", active=active_count)
        else:
            text = tr("recommendations.feed.count", count=active_count)
        self._deck_status_label.setText(text)
        self._deck_status_label.show()

    def _load_recommendation_deck(self, *, force_new: bool) -> None:
        if not self._recommendations_active:
            self._deck_dirty = True
            return
        self._new_deck_button.setEnabled(False)
        self._deck_status_label.setText(tr("recommendations.state.loading"))
        self._deck_status_label.show()
        try:
            deck = self._deck_service.refresh_deck(
                self._deck_preferences(),
                datetime.now(timezone.utc),
                force_new=force_new,
            )
        except Exception:
            logger.exception("recommendation deck build failed")
            self._deck = None
            self._all_candidates = []
            self._candidates = []
            self._model.set_candidates([])
            self._deck_status_label.setText(tr("recommendations.state.local_error"))
            self._clear_detail(show_filters_hint=False)
            return
        finally:
            self._new_deck_button.setEnabled(True)

        self._deck = deck
        self._deck_dirty = False
        self._all_candidates = list(deck.get("active") or [])[:30]
        self._pool_unique_total = len(self._all_candidates)
        self._detail_entries = {}
        self._search_index = build_candidate_search_index(self._all_candidates)
        self._update_deck_status()
        self._apply_visible_candidates()
        if not self._all_candidates:
            self._clear_detail(show_filters_hint=False)

    def _on_new_deck_clicked(self) -> None:
        self._load_recommendation_deck(force_new=True)

    def _apply_recommendation_action(self, action: str) -> None:
        candidate = self._selected_candidate
        deck = self._deck
        if not isinstance(candidate, dict) or not isinstance(deck, dict):
            return
        current_row = self._results_list.currentIndex().row()
        try:
            updated = self._deck_service.apply_action_and_refill(
                str(deck["deck_id"]),
                candidate,
                action,
            )
        except Exception:
            logger.exception("recommendation action failed: %s", action)
            self._deck_status_label.setText(tr("recommendations.action.failed"))
            self._deck_status_label.show()
            return

        self._deck = updated
        self._all_candidates = list(updated.get("active") or [])[:30]
        self._pool_unique_total = len(self._all_candidates)
        self._detail_entries.pop(candidate_detail_identity(candidate), None)
        self._selected_candidate = None
        self._selected_identity = None
        self._search_index = build_candidate_search_index(self._all_candidates)
        self._apply_visible_candidates()
        if self._candidates:
            row = min(max(0, current_row), len(self._candidates) - 1)
            self._results_list.setCurrentIndex(self._model.index(row, 0))
        else:
            self._clear_detail(show_filters_hint=False)
        self._update_deck_status()
        if self._candidates:
            self._deck_status_label.setText(tr(f"recommendations.action.done.{action}"))
        # TODO: add transactional undo when the shell supports actionable toast notifications.
        if action == "watched" and self._on_watched_added is not None:
            self._on_watched_added(updated.get("last_action", {}).get("transition"))

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

    def _fts_search_enabled(self) -> bool:
        return bool(getattr(self._service, "is_fts_search_enabled", lambda: False)())

    def _detail_search_context(self) -> dict | None:
        if self._fts_search_enabled() is False:
            return None
        context = dict(self._session.last_search_context() or {})
        text_query = str(context.get("text_query") or self._search_input.text() or "").strip()
        if text_query == "":
            return None
        context["text_query"] = text_query
        return context

    def _build_detail_entry(self, candidate: dict) -> tuple:
        return build_candidate_readonly_detail_entry(
            candidate,
            data_language=self._data_language,
            filters=self._session.filters,
            search_context=self._detail_search_context(),
        )

    def _on_search_query_changed(self) -> None:
        self._apply_visible_candidates()

    def _apply_visible_candidates(self) -> None:
        query = self._search_input.text()
        previous_identity = self._selected_identity
        self._candidates = self._search_index.filter_by_query(query)
        self._log_search_query(query)

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

        self._restore_result_selection(previous_identity)

    def _restore_result_selection(self, previous_identity: str | None) -> None:
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

    def _log_search_query(self, query: str) -> None:
        """Best-effort: log one finalized search result (deduped, never raises)."""
        try:
            from candidates.search import query_log

            if not query_log.is_search_query_log_enabled():
                return
            context = self._session.last_search_context() or {}
            text_query = str(context.get("text_query") or query or "")
            entry = query_log.build_search_query_entry(
                search_id=context.get("search_id"),
                query=query,
                filters=context.get("filters"),
                sort_mode=context.get("sort_mode") or self._session.sort_mode,
                result_count=len(self._candidates),
                top_candidates=self._candidates,
                latency_ms=context.get("latency_ms"),
                text_query=text_query,
                fts_enabled=self._fts_search_enabled(),
            )
            signature = query_log.build_search_signature(entry)
            if signature == self._last_logged_search_signature:
                return
            self._last_logged_search_signature = signature
            query_log.append_search_query_log(entry)
        except Exception:
            logger.debug("search query logging skipped", exc_info=True)

    def _update_counter_label(self, query: str) -> None:
        visible = len(self._candidates)
        total = len(self._all_candidates)
        if query.strip():
            self._counter_label.setText(
                tr(
                    "recommendations.counter.found",
                    visible=visible,
                    total=total,
                )
            )
        else:
            self._counter_label.setText(
                tr(
                    "recommendations.counter.shown",
                    visible=visible,
                )
            )

    def refresh(self) -> None:
        self._refresh_data_language()
        self._poster_request_seq += 1
        self._deck_dirty = True
        if self._recommendations_active and not self._session.is_loading:
            self._load_recommendation_deck(force_new=False)

    def _on_result_selected(self, current: QModelIndex, _previous: QModelIndex = QModelIndex()) -> None:
        started = perf_counter()
        row = current.row() if current.isValid() else -1
        if row < 0 or row >= len(self._candidates):
            if self._deck is not None and len(self._candidates) == 0:
                self._clear_detail(
                    show_filters_hint=False,
                    search_active=bool(self._search_input.text().strip()),
                )
            else:
                self._clear_detail(show_filters_hint=self._deck is None)
            return

        candidate = self._candidates[row]
        self._selected_candidate = candidate
        self._selected_identity = candidate_detail_identity(candidate)
        self._log_search_action("open", candidate, rank=row + 1)
        lookup_done = perf_counter()

        identity = candidate_detail_identity(candidate)
        self._poster_request_seq += 1
        request_seq = self._poster_request_seq
        entry = self._detail_entries.get(identity)
        if entry is None:
            entry = self._build_detail_entry(candidate)
            self._detail_entries[identity] = entry
        build_done = perf_counter()

        self._detail_placeholder.hide()
        self._detail_scroll.show()
        self._show_detail_entry(entry)
        self._set_action_panel_enabled(True)
        self._update_recommendation_reasons(candidate)
        render_done = perf_counter()

        poster_url = candidate_poster_url_for_download(
            candidate,
            data_language=self._data_language,
        )
        if poster_url not in (None, ""):
            self._start_poster_download(poster_url, identity, request_seq)
        self._start_localized_poster_enrichment(candidate, identity, request_seq)

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

    def _candidate_has_tmdb_id(self, candidate: dict) -> bool:
        if candidate.get("tmdb_id") not in (None, ""):
            return True
        source_query = candidate.get("source_query")
        return isinstance(source_query, dict) and source_query.get("tmdb_id") not in (None, "")

    def _start_localized_poster_enrichment(self, candidate: dict, identity: str, request_seq: int) -> None:
        if isinstance(candidate, dict) is False:
            return
        if self._candidate_has_tmdb_id(candidate) is False:
            return
        if candidate_needs_tmdb_detail_enrichment(candidate, self._data_language) is False:
            return

        worker_key = f"{self._data_language}:{identity}"
        if worker_key in self._localized_poster_inflight:
            return
        self._localized_poster_inflight.add(worker_key)

        worker = CandidateLocalizedPosterWorker(identity, candidate, self._data_language, parent=self._widget)
        worker.finished_with_candidate.connect(
            lambda ident, updated, changed, seq=request_seq: self._on_localized_poster_enriched(
                seq,
                ident,
                updated,
                changed,
            )
        )
        worker.finished.connect(
            lambda worker=worker, key=worker_key: self._remove_localized_poster_worker(worker, key)
        )
        worker.finished.connect(worker.deleteLater)
        self._localized_poster_workers.append(worker)
        worker.start()

    def _remove_localized_poster_worker(self, worker: CandidateLocalizedPosterWorker, worker_key: str = "") -> None:
        self._localized_poster_workers = [
            item
            for item in self._localized_poster_workers
            if item is not worker
        ]
        if worker_key:
            self._localized_poster_inflight.discard(worker_key)

    def _replace_candidate_by_identity(self, identity: str, updated_candidate: dict) -> dict | None:
        replacement = None
        for candidates in (self._all_candidates, self._candidates):
            for index, candidate in enumerate(candidates):
                if candidate_detail_identity(candidate) != identity:
                    continue
                candidate.clear()
                candidate.update(updated_candidate)
                candidates[index] = candidate
                replacement = candidate
        return replacement

    def _on_localized_poster_enriched(
        self,
        request_seq: int,
        identity: str,
        updated_candidate: dict,
        changed: bool,
    ) -> None:
        if changed is not True or isinstance(updated_candidate, dict) is False:
            return

        candidate = self._replace_candidate_by_identity(identity, updated_candidate)
        if candidate is None:
            candidate = updated_candidate
        self._detail_entries.pop(identity, None)
        self._model.update_poster_path(identity, None)
        self._results_list.viewport().update()

        if request_seq != self._poster_request_seq or self._selected_identity != identity:
            return

        self._selected_candidate = candidate
        entry = self._build_detail_entry(candidate)
        self._detail_entries[identity] = entry
        self._show_detail_entry(entry)

        poster_url = candidate_poster_url_for_download(
            candidate,
            data_language=self._data_language,
        )
        if poster_url not in (None, ""):
            self._start_poster_download(poster_url, identity, request_seq)

    def _on_loading_changed(self) -> None:
        if self._session.is_loading:
            self._counter_label.setText(tr("recommendations.state.replenishing"))
            self._clear_detail(show_filters_hint=False, loading=True)
        elif self._recommendations_active and self._deck_dirty:
            self._load_recommendation_deck(force_new=False)

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
        self._set_action_panel_enabled(False)
        if loading:
            self._detail_placeholder.setText(tr("recommendations.state.replenishing"))
            self._detail_placeholder.show()
        elif show_filters_hint:
            self._detail_placeholder.setText(tr("recommendations.state.open_hint"))
            self._detail_placeholder.show()
        elif search_active:
            self._detail_placeholder.setText(tr("candidates.detail.no_results_query"))
            self._detail_placeholder.show()
        elif len(self._candidates) == 0:
            self._detail_placeholder.setText(tr("recommendations.state.empty"))
            self._detail_placeholder.show()
        else:
            self._detail_placeholder.setText(tr("candidates.detail.select_candidate"))
            self._detail_placeholder.show()
