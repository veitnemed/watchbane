"""Desktop Candidates tab: card list and read-only detail card."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from math import ceil
from time import perf_counter

from PyQt6.QtCore import QModelIndex, QSize, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from candidates.pool.localized_posters import candidate_needs_tmdb_detail_enrichment
from candidates.deck_reserve_presentation import resolve_deck_reserve_presentation
from candidates.recommendation_deck_service import ACTIVE_DECK_SIZE, RecommendationDeckService
from candidates.scoring.rating_confidence import has_unknown_rating
from desktop.candidates.empty_state import RecommendationEmptyState
from desktop.candidates.deck_reserve_indicator import DeckReserveIndicator
from desktop.candidates.list_actions import CandidateListActionsMixin
from desktop.candidates.list_delegate import build_candidate_list_item_delegate
from desktop.candidates.filter_icon_assets import filter_section_badge_label
from desktop.candidates.list_model import CandidateListModel
from desktop.candidates.poster_prefetch import CandidatePosterPrefetchController
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
from desktop.shared.widgets.user_rating_selector import UserRatingSelector
from desktop.theme.shell_layout import (
    CANDIDATE_DETAIL_COLLAPSE_WIDTH_PX,
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
from desktop.theme.tokens import FILM_ACCENT, FILM_ACCENT_DIM, FILM_BORDER

logger = logging.getLogger(__name__)

CANDIDATE_LIST_STRETCH = 0
CANDIDATE_DETAIL_STRETCH = 1
CANDIDATE_LIST_ITEM_SPACING = list_px(2)
POSTER_PRIORITY_COUNT = 8
POSTER_READY_TARGET = 20
POSTER_REVEAL_DEADLINE_MS = 8_000
POSTER_MIN_LOADER_MS = 180
REFILL_RETRY_COOLDOWN_SECONDS = 30.0


class _CandidateListRoot(QWidget):
    hidden = pyqtSignal()
    resized = pyqtSignal()

    def hideEvent(self, event) -> None:
        self.hidden.emit()
        super().hideEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self.resized.emit()

class CandidateListView(CandidateListActionsMixin):
    """Recommendations tab backed by a bounded, refillable candidate deck."""

    def __init__(
        self,
        session: CandidateSearchSession,
        *,
        service=None,
        deck_service: RecommendationDeckService | None = None,
        on_watched_added: Callable[[object], None] | None = None,
        on_refill_needed: Callable[[dict], bool] | None = None,
    ) -> None:
        self._session = session
        self._service = service or session.service
        self._deck_service = deck_service or RecommendationDeckService(
            pool_loader=self._load_pool_for_deck,
        )
        self._on_watched_added = on_watched_added
        self._on_refill_needed = on_refill_needed
        self._data_language = get_persisted_data_language()
        self._all_candidates: list[dict] = []
        self._candidates: list[dict] = []
        self._selected_candidate: dict | None = None
        self._selected_identity: str | None = None
        self._search_index = build_candidate_search_index([])
        self._pool_unique_total = 0
        self._detail_entries: dict[str, tuple] = {}
        self._poster_request_seq = 0
        self._localized_poster_workers: list[CandidateLocalizedPosterWorker] = []
        self._localized_poster_inflight: set[str] = set()
        self._pending_localized_poster: tuple[dict, str, int] | None = None
        self._model = CandidateListModel(parent=None, data_language=self._data_language)
        self._delegate = None
        self._last_logged_search_signature: tuple | None = None
        self._deck: dict | None = None
        self._recommendations_active = False
        self._deck_dirty = True
        self._deck_load_scheduled = False
        self._poster_prefetch_busy = False
        self._poster_prefetch_failed = 0
        self._refill_requested_deck_ids: set[str] = set()
        self._refill_last_attempt: tuple[str, float] | None = None
        self._deck_prepare_active = False
        self._deck_prepare_batch_id: int | None = None
        self._deck_prepare_started_at = 0.0
        self._deck_loader_shown_at = 0.0
        self._pending_reveal_batch_id: int | None = None
        self._pending_reveal_reason = ""
        self._deck_prepare_priority_identities: set[str] = set()
        self._deck_prepare_settled_identities: set[str] = set()
        self._deck_prepare_total = 0
        self._deck_prepare_ready = 0
        self._deck_prepare_failed = 0
        self._deck_prepare_settled = 0
        self._deck_prepare_cache_hits = 0
        self._deck_build_ms = 0.0
        self._initial_deck_loaded = False
        self._active_workspace_state: str | None = None
        self._deck_build_in_progress = False
        self._deck_build_failed = False
        self._deck_replenishing_active = False

        self._widget = _CandidateListRoot()
        self._widget.setObjectName("candidateListRoot")
        self._deck_load_timer = QTimer(self._widget)
        self._deck_load_timer.setSingleShot(True)
        self._deck_load_timer.timeout.connect(self._run_scheduled_deck_load)
        self._deck_deadline_timer = QTimer(self._widget)
        self._deck_deadline_timer.setSingleShot(True)
        self._deck_deadline_timer.timeout.connect(self._on_deck_deadline)
        self._deck_minimum_timer = QTimer(self._widget)
        self._deck_minimum_timer.setSingleShot(True)
        self._deck_minimum_timer.timeout.connect(self._on_deck_minimum_elapsed)
        self._widget.hidden.connect(self._on_root_hidden)
        self._poster_prefetch = CandidatePosterPrefetchController(parent=self._widget)
        self._poster_prefetch.poster_ready.connect(self._on_poster_prefetch_ready)
        self._poster_prefetch.busy_changed.connect(self._on_poster_prefetch_busy_changed)
        self._poster_prefetch.network_cycle_finished.connect(
            self._on_poster_prefetch_network_cycle_finished
        )
        self._poster_prefetch.batch_started.connect(self._on_poster_batch_started)
        self._poster_prefetch.candidate_settled.connect(self._on_poster_candidate_settled)
        self._poster_prefetch.batch_progress.connect(self._on_poster_batch_progress)
        self._poster_prefetch.batch_finished.connect(self._on_poster_prefetch_batch_finished)
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

        self._deck_stack = QStackedWidget(self._widget)
        self._deck_stack.setObjectName("recommendationsDeckStack")
        root_layout.addWidget(self._deck_stack, stretch=1)

        self._deck_loading_page = QWidget(self._deck_stack)
        self._deck_loading_page.setObjectName("recommendationsDeckLoadingPage")
        loading_layout = QHBoxLayout(self._deck_loading_page)
        loading_layout.setContentsMargins(
            0,
            LEFT_PANEL_TOP_COMPENSATION_PX,
            0,
            0,
        )
        loading_layout.setSpacing(CANDIDATE_ROOT_SPACING_PX)

        self._deck_loading_list_shell = QWidget()
        self._deck_loading_list_shell.setObjectName("recommendationsLoadingListShell")
        self._deck_loading_list_shell.setMinimumWidth(CANDIDATE_LIST_MIN_WIDTH_PX)
        self._deck_loading_list_shell.setMaximumWidth(CANDIDATE_LIST_MAX_WIDTH_PX)
        loading_list_layout = QVBoxLayout(self._deck_loading_list_shell)
        loading_list_layout.setContentsMargins(0, 0, 0, 0)
        loading_list_layout.setSpacing(CANDIDATE_LIST_SPACING_PX)
        loading_feed_title = QLabel(tr("recommendations.feed.title"))
        loading_feed_title.setObjectName("recommendationsFeedTitle")
        loading_list_layout.addWidget(loading_feed_title)
        loading_list_placeholder = QFrame()
        loading_list_placeholder.setObjectName("recommendationsLoadingListPlaceholder")
        loading_list_layout.addWidget(loading_list_placeholder, stretch=1)
        loading_layout.addWidget(self._deck_loading_list_shell)

        self._deck_loading_state = RecommendationEmptyState("loading")
        self._deck_loading_progress = QProgressBar(self._deck_loading_page)
        self._deck_loading_progress.setObjectName("recommendationsDeckLoadingProgress")
        self._deck_loading_progress.setRange(0, ACTIVE_DECK_SIZE)
        self._deck_loading_progress.setValue(0)
        self._deck_loading_progress.setTextVisible(True)
        self._deck_loading_progress.setFormat(
            tr("recommendations.preparing.progress", settled=0, total=ACTIVE_DECK_SIZE)
        )
        self._deck_loading_progress.setMinimumWidth(list_px(320))
        self._deck_loading_progress.setMaximumWidth(list_px(420))
        self._deck_loading_state.add_accessory(self._deck_loading_progress)
        loading_layout.addWidget(self._deck_loading_state, stretch=1)
        self._deck_stack.addWidget(self._deck_loading_page)

        self._deck_content_page = QWidget(self._deck_stack)
        self._deck_content_page.setObjectName("recommendationsDeckContentPage")
        content_layout = QVBoxLayout(self._deck_content_page)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal, self._deck_content_page)
        content_layout.addWidget(splitter)
        self._deck_stack.addWidget(self._deck_content_page)
        self._deck_stack.setCurrentWidget(self._deck_content_page)

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
        self._deck_reserve_label = QLabel(tr("recommendations.deck_reserve.label"))
        self._deck_reserve_label.setObjectName("recommendationsDeckReserveLabel")
        feed_header_layout.addWidget(self._deck_reserve_label)
        self._deck_reserve_indicator = DeckReserveIndicator(feed_header)
        feed_header_layout.addWidget(self._deck_reserve_indicator)
        self._deck_refill_button = QPushButton(tr("recommendations.deck_reserve.refresh"))
        self._deck_refill_button.setObjectName("recommendationsDeckRefillButton")
        self._deck_refill_button.clicked.connect(self._on_deck_refill_clicked)
        self._deck_refill_button.hide()
        feed_header_layout.addWidget(self._deck_refill_button)
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
        self._list_body_stack = QStackedWidget()
        self._list_body_stack.setObjectName("recommendationsListBodyStack")
        self._list_body_stack.addWidget(self._results_list)
        self._compact_workspace_state = RecommendationEmptyState("idle", compact=True)
        self._list_body_stack.addWidget(self._compact_workspace_state)
        self._list_body_stack.setCurrentWidget(self._results_list)
        list_layout.addWidget(self._list_body_stack, stretch=1)
        self._counter_label.hide()
        splitter.addWidget(list_panel)

        detail_panel = QWidget()
        detail_panel.setObjectName("candidateSearchDetailPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, LEFT_PANEL_TOP_COMPENSATION_PX, 0, 0)
        detail_layout.setSpacing(0)

        self._workspace_state = RecommendationEmptyState("idle")
        detail_layout.addWidget(self._workspace_state, stretch=1)

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

        self._decision_cluster = QWidget()
        self._decision_cluster.setObjectName("recommendationDecisionCluster")
        decision_layout = QVBoxLayout(self._decision_cluster)
        decision_layout.setContentsMargins(0, 0, 0, 0)
        decision_layout.setSpacing(list_px(10))

        self._reason_panel = QFrame()
        self._reason_panel.setObjectName("recommendationReasonsPanel")
        reason_layout = QHBoxLayout(self._reason_panel)
        reason_layout.setContentsMargins(
            list_px(14),
            list_px(10),
            list_px(14),
            list_px(10),
        )
        reason_layout.setSpacing(list_px(12))
        reason_icon = filter_section_badge_label(
            "bookmark",
            "recommendationReasonsIcon",
            list_px(34),
            FILM_ACCENT,
            FILM_ACCENT_DIM,
            FILM_BORDER,
        )
        reason_layout.addWidget(reason_icon, alignment=Qt.AlignmentFlag.AlignVCenter)
        reason_copy = QWidget()
        reason_copy.setObjectName("recommendationReasonsCopy")
        reason_copy_layout = QVBoxLayout(reason_copy)
        reason_copy_layout.setContentsMargins(0, 0, 0, 0)
        reason_copy_layout.setSpacing(list_px(7))
        self._reason_title = QLabel(tr("recommendations.reasons.title"))
        self._reason_title.setObjectName("recommendationReasonsTitle")
        reason_copy_layout.addWidget(self._reason_title)
        self._reason_label = QLabel("")
        self._reason_label.setObjectName("recommendationReasonsText")
        self._reason_label.setWordWrap(True)
        reason_copy_layout.addWidget(self._reason_label)
        reason_layout.addWidget(reason_copy, stretch=1)

        self._action_panel = QFrame()
        self._action_panel.setObjectName("recommendationActionPanel")
        action_layout = QVBoxLayout(self._action_panel)
        action_layout.setContentsMargins(
            list_px(14),
            list_px(12),
            list_px(14),
            list_px(14),
        )
        action_layout.setSpacing(list_px(12))

        action_buttons_layout = QGridLayout()
        action_buttons_layout.setContentsMargins(0, 0, 0, 0)
        action_buttons_layout.setHorizontalSpacing(list_px(12))
        action_buttons_layout.setVerticalSpacing(list_px(10))
        self._watched_action_button = QPushButton(tr("recommendations.action.watched"))
        self._watched_action_button.setObjectName("recommendationWatchedButton")
        self._watched_action_button.hide()
        self._watchlist_action_button = QPushButton(tr("recommendations.action.watchlist"))
        self._watchlist_action_button.setObjectName("recommendationWatchlistButton")
        self._hidden_action_button = QPushButton(tr("recommendations.action.hidden"))
        self._hidden_action_button.setObjectName("recommendationHiddenButton")
        rating_prompt = QLabel(tr("user_rating.candidate_prompt"))
        rating_prompt.setObjectName("recommendationUserRatingPrompt")
        rating_prompt.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        action_layout.addWidget(rating_prompt)
        self._candidate_rating_selector = UserRatingSelector()
        self._candidate_rating_selector.setObjectName("recommendationUserRatingSelector")
        self._candidate_rating_selector.setProperty("candidatePanel", True)
        self._candidate_rating_selector.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        for button in self._candidate_rating_selector.buttons():
            button.setMinimumWidth(list_px(72))
            button.setMinimumHeight(list_px(40))
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            button.setIconSize(QSize(list_px(18), list_px(18)))
        self._candidate_rating_selector.valueChanged.connect(
            lambda value: self._apply_recommendation_action("watched", user_score=value)
            if value is not None
            else None
        )
        rating_row = QHBoxLayout()
        rating_row.setContentsMargins(0, 0, 0, 0)
        rating_row.setSpacing(0)
        rating_row.addWidget(self._candidate_rating_selector, stretch=1)
        action_layout.addLayout(rating_row)
        self._watchlist_action_button.clicked.connect(
            lambda: self._apply_recommendation_action("watchlist")
        )
        self._hidden_action_button.clicked.connect(
            lambda: self._apply_recommendation_action("hidden")
        )
        action_buttons = (self._watchlist_action_button, self._hidden_action_button)
        for button in action_buttons:
            button.setMinimumHeight(list_px(38))
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        if detail_profiles.use_compact_detail_content():
            for index, button in enumerate(action_buttons):
                action_buttons_layout.addWidget(button, 0, index)
                action_buttons_layout.setColumnStretch(index, 1)
        else:
            for column, button in enumerate(action_buttons):
                action_buttons_layout.addWidget(button, 0, column)
                action_buttons_layout.setColumnStretch(column, 1)
        action_layout.addLayout(action_buttons_layout)
        decision_layout.addWidget(self._action_panel)
        self._detail_card.add_overview_footer(self._reason_panel)
        self._detail_card.add_main_info_footer(self._decision_cluster)
        self._set_action_panel_enabled(False)

        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, CANDIDATE_LIST_STRETCH)
        splitter.setStretchFactor(1, CANDIDATE_DETAIL_STRETCH)
        splitter.setSizes([CANDIDATE_SPLITTER_LIST_DEFAULT_PX, CANDIDATE_SPLITTER_DETAIL_DEFAULT_PX])

        self._splitter = splitter
        self._list_panel = list_panel
        self._detail_panel = detail_panel
        self._expanded_splitter_sizes = [
            CANDIDATE_SPLITTER_LIST_DEFAULT_PX,
            CANDIDATE_SPLITTER_DETAIL_DEFAULT_PX,
        ]
        self._is_compact_layout: bool | None = None
        self._widget.resized.connect(self._update_responsive_layout)
        self._update_responsive_layout()

        session.add_listener(self.refresh)
        session.add_loading_listener(self._on_loading_changed)
        self._clear_detail(show_filters_hint=True)
        self._update_deck_reserve_indicator()

    def _is_deck_replenishing(self) -> bool:
        return self._session.is_loading or self._deck_replenishing_active

    def _update_deck_reserve_indicator(self) -> None:
        indicator = getattr(self, "_deck_reserve_indicator", None)
        if indicator is None:
            return
        presentation = resolve_deck_reserve_presentation(
            recommendations_active=self._recommendations_active,
            deck=self._deck,
            deck_build_in_progress=self._deck_build_in_progress,
            deck_load_scheduled=self._deck_load_scheduled,
            deck_prepare_active=self._deck_prepare_active,
            session_loading=self._session.is_loading,
            replenishing_for_deck=self._is_deck_replenishing(),
            build_failed=self._deck_build_failed,
            offline=bool(self._session.last_error),
        )
        indicator.apply_presentation(presentation)
        self._deck_reserve_label.setVisible(presentation.mode != "idle")
        snapshot = presentation.snapshot
        retry_build = presentation.mode == "error"
        self._deck_refill_button.setText(
            tr(
                "recommendations.deck_reserve.retry"
                if retry_build
                else "recommendations.deck_reserve.refresh"
            )
        )
        self._deck_refill_button.setVisible(
            retry_build
            or (
                presentation.mode == "ready"
                and snapshot is not None
                and snapshot.remaining < 25
                and self._on_refill_needed is not None
            )
        )

    def _on_deck_refill_clicked(self) -> None:
        if self._deck is None:
            self._deck_build_failed = False
            self._load_recommendation_deck(force_new=False)
            return
        deck_id = str((self._deck or {}).get("deck_id") or "")
        if deck_id:
            self._refill_requested_deck_ids.discard(deck_id)
            self._refill_last_attempt = None
        self._maybe_request_recommendation_refill()

    def on_tab_activated(self) -> None:
        self._refresh_data_language()
        self._recommendations_active = True
        if self._deck_load_scheduled:
            self._update_deck_reserve_indicator()
            return
        if self._deck is None and not self._deck_prepare_active:
            self._begin_deck_preparation()
        self._deck_load_scheduled = True
        self._deck_status_label.setText(tr("recommendations.state.loading"))
        self._deck_status_label.show()
        self._deck_load_timer.start(25)
        self._update_deck_reserve_indicator()

    def _run_scheduled_deck_load(self) -> None:
        self._deck_load_scheduled = False
        if self._recommendations_active:
            self._load_recommendation_deck(force_new=False)

    def _on_root_hidden(self) -> None:
        if not self._deck_load_timer.isActive():
            return
        self._deck_load_timer.stop()
        self._deck_load_scheduled = False
        self._deck_dirty = True
        self._update_deck_reserve_indicator()

    @property
    def widget(self) -> QWidget:
        return self._widget

    def _update_responsive_layout(self, available_width: int | None = None) -> None:
        viewport_width = self._widget.width() if available_width is None else available_width
        compact = viewport_width < CANDIDATE_DETAIL_COLLAPSE_WIDTH_PX
        was_compact = self._is_compact_layout
        if compact == was_compact:
            return

        self._is_compact_layout = compact
        self._deck_loading_list_shell.setVisible(not compact)
        self._deck_loading_state.set_compact(compact)
        if compact:
            if was_compact is False:
                sizes = self._splitter.sizes()
                if len(sizes) == 2 and sizes[1] > 0:
                    self._expanded_splitter_sizes = sizes
            self._list_panel.setMaximumWidth(self._widget.maximumWidth())
            self._detail_panel.hide()
            self._splitter.handle(1).hide()
            self._splitter.setSizes([max(1, self._widget.width()), 0])
            self._sync_workspace_state_surface()
            return

        self._list_panel.setMaximumWidth(CANDIDATE_LIST_MAX_WIDTH_PX)
        self._detail_panel.show()
        self._splitter.handle(1).show()
        self._splitter.setSizes(self._expanded_splitter_sizes)
        self._sync_workspace_state_surface()

    def _show_workspace_state(self, state: str) -> None:
        self._active_workspace_state = state
        self._workspace_state.set_state(state)
        self._compact_workspace_state.set_state(state)
        self._sync_workspace_state_surface()

    def _hide_workspace_state(self) -> None:
        self._active_workspace_state = None
        self._sync_workspace_state_surface()

    def on_replenish_state_changed(self, state: str) -> None:
        """Reflect filter-worker lifecycle only when there is no usable list content."""
        deck_id = str((self._deck or {}).get("deck_id") or "")
        if state in {"error", "finished"} and deck_id:
            self._refill_requested_deck_ids.discard(deck_id)
            self._refill_last_attempt = (deck_id, perf_counter())
        if state == "finished" and self._recommendations_active:
            QTimer.singleShot(0, self.refresh)
        if self._candidates:
            return
        if state == "loading":
            self._clear_detail(show_filters_hint=False, loading=True)
            return
        if state == "error":
            self._clear_detail(show_filters_hint=False, error=True)
            self._show_deck_content()
            return
        if state == "finished":
            self._clear_detail(show_filters_hint=False)
            self._show_deck_content()

    def _sync_workspace_state_surface(self) -> None:
        state_visible = self._active_workspace_state is not None
        if state_visible and self._is_compact_layout and not self._candidates:
            self._workspace_state.hide()
            self._list_body_stack.setCurrentWidget(self._compact_workspace_state)
            return
        self._list_body_stack.setCurrentWidget(self._results_list)
        self._workspace_state.setVisible(state_visible)

    def _load_pool_for_deck(self) -> dict:
        view = self._session.overview()
        candidates = (view.get("candidates") or []) if isinstance(view, dict) else []
        return {
            candidate_detail_identity(candidate): candidate
            for candidate in candidates
            if isinstance(candidate, dict)
        }

    def _deck_preferences(self) -> dict:
        return dict(self._session.filters or DEFAULT_BROWSE_FILTERS)

    def _deck_vector(self) -> dict:
        return dict(self._session.recommendation_vector)

    def _set_action_panel_enabled(self, enabled: bool) -> None:
        self._decision_cluster.setVisible(enabled)
        self._reason_panel.setVisible(enabled)
        self._action_panel.setVisible(enabled)
        for button in (
            self._watched_action_button,
            self._watchlist_action_button,
            self._hidden_action_button,
        ):
            button.setEnabled(enabled)
        self._candidate_rating_selector.setEnabled(enabled)
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
        elif self._poster_prefetch_busy:
            text = tr("recommendations.feed.loading_posters", count=active_count)
        elif self._poster_prefetch_failed > 0:
            text = tr("recommendations.feed.posters_unavailable", count=active_count)
        else:
            text = tr("recommendations.feed.count", count=active_count)
        self._deck_status_label.setText(text)
        self._deck_status_label.setToolTip(
            tr("recommendations.feed.posters_unavailable_hint")
            if self._poster_prefetch_failed > 0 and not self._poster_prefetch_busy
            else ""
        )
        self._deck_status_label.setVisible(active_count > 0)
        self._update_deck_reserve_indicator()

    def _on_poster_prefetch_busy_changed(self, busy: bool) -> None:
        self._poster_prefetch_busy = bool(busy)
        if busy:
            self._poster_prefetch_failed = 0
        if self._deck is not None:
            self._update_deck_status()

    def _on_poster_prefetch_network_cycle_finished(self, _succeeded: int, failed: int) -> None:
        self._poster_prefetch_failed = max(0, int(failed))
        if self._deck is not None:
            self._update_deck_status()

    def _begin_deck_preparation(self) -> None:
        self._deck_deadline_timer.stop()
        self._deck_minimum_timer.stop()
        self._deck_prepare_active = True
        self._deck_prepare_batch_id = None
        self._deck_prepare_started_at = 0.0
        self._deck_loader_shown_at = perf_counter()
        self._pending_reveal_batch_id = None
        self._pending_reveal_reason = ""
        self._deck_prepare_priority_identities = set()
        self._deck_prepare_settled_identities = set()
        self._deck_prepare_total = 0
        self._deck_prepare_ready = 0
        self._deck_prepare_failed = 0
        self._deck_prepare_settled = 0
        self._deck_prepare_cache_hits = 0
        self._deck_loading_progress.setRange(0, ACTIVE_DECK_SIZE)
        self._deck_loading_progress.setValue(0)
        self._deck_loading_progress.setFormat(
            tr("recommendations.preparing.progress", settled=0, total=ACTIVE_DECK_SIZE)
        )
        self._deck_loading_state.set_state("loading")
        self._deck_stack.setCurrentWidget(self._deck_loading_page)
        self._update_deck_reserve_indicator()

    def _show_deck_content(self) -> None:
        self._deck_deadline_timer.stop()
        self._deck_minimum_timer.stop()
        self._deck_prepare_active = False
        self._deck_stack.setCurrentWidget(self._deck_content_page)
        self._update_deck_reserve_indicator()

    def _on_poster_batch_started(self, batch_id: int, total: int) -> None:
        if not self._deck_prepare_active:
            return
        self._deck_deadline_timer.stop()
        self._deck_minimum_timer.stop()
        self._deck_prepare_batch_id = int(batch_id)
        self._deck_prepare_started_at = perf_counter()
        self._pending_reveal_batch_id = None
        self._pending_reveal_reason = ""
        self._deck_prepare_settled_identities = set()
        self._deck_prepare_total = max(0, int(total))
        self._deck_prepare_ready = 0
        self._deck_prepare_failed = 0
        self._deck_prepare_settled = 0
        self._deck_prepare_cache_hits = 0
        progress_maximum = max(1, self._deck_prepare_total)
        self._deck_loading_progress.setRange(0, progress_maximum)
        self._deck_loading_progress.setValue(0)
        self._deck_loading_progress.setFormat(
            tr(
                "recommendations.preparing.progress",
                settled=0,
                total=self._deck_prepare_total,
            )
        )
        self._deck_deadline_timer.start(POSTER_REVEAL_DEADLINE_MS)

    def _on_deck_deadline(self) -> None:
        batch_id = self._deck_prepare_batch_id
        if batch_id is not None:
            self._request_deck_reveal(batch_id, "deadline")

    def _on_deck_minimum_elapsed(self) -> None:
        batch_id = self._pending_reveal_batch_id
        reason = self._pending_reveal_reason
        if batch_id is not None:
            self._request_deck_reveal(batch_id, reason)

    def _on_poster_candidate_settled(
        self,
        batch_id: int,
        identity: str,
        _local_path: str,
        _failed: bool,
        _cache_hit: bool,
    ) -> None:
        if batch_id != self._deck_prepare_batch_id:
            return
        self._deck_prepare_settled_identities.add(str(identity))

    def _on_poster_batch_progress(
        self,
        batch_id: int,
        ready: int,
        failed: int,
        settled: int,
        total: int,
        cache_hits: int,
    ) -> None:
        if batch_id != self._deck_prepare_batch_id:
            return
        self._deck_prepare_ready = max(0, int(ready))
        self._deck_prepare_failed = max(0, int(failed))
        self._deck_prepare_settled = max(0, int(settled))
        self._deck_prepare_total = max(0, int(total))
        self._deck_prepare_cache_hits = max(0, int(cache_hits))
        self._deck_loading_progress.setRange(0, max(1, self._deck_prepare_total))
        self._deck_loading_progress.setValue(
            min(self._deck_prepare_settled, max(1, self._deck_prepare_total))
        )
        self._deck_loading_progress.setFormat(
            tr(
                "recommendations.preparing.progress",
                settled=self._deck_prepare_settled,
                total=self._deck_prepare_total,
            )
        )
        all_settled = self._deck_prepare_settled >= self._deck_prepare_total
        priority_settled = self._deck_prepare_priority_identities.issubset(
            self._deck_prepare_settled_identities
        )
        target_settled = self._deck_prepare_settled >= POSTER_READY_TARGET
        if all_settled or (priority_settled and target_settled):
            reason = "all_settled" if all_settled else "priority_target"
            self._request_deck_reveal(batch_id, reason)

    def _request_deck_reveal(self, batch_id: int, reason: str) -> None:
        if (
            not self._deck_prepare_active
            or batch_id != self._deck_prepare_batch_id
        ):
            return
        loader_elapsed_ms = (perf_counter() - self._deck_loader_shown_at) * 1000.0
        if self._deck_prepare_total > 0 and loader_elapsed_ms < POSTER_MIN_LOADER_MS:
            self._pending_reveal_batch_id = batch_id
            self._pending_reveal_reason = reason
            self._deck_minimum_timer.start(
                max(1, ceil(POSTER_MIN_LOADER_MS - loader_elapsed_ms))
            )
            return
        reveal_ms = (
            (perf_counter() - self._deck_prepare_started_at) * 1000.0
            if self._deck_prepare_started_at > 0.0
            else 0.0
        )
        self._show_deck_content()
        logger.info(
            "recommendation deck revealed deck_id=%s deck_build_ms=%.1f "
            "poster_total=%d poster_cache_hits=%d poster_ready_at_reveal=%d "
            "poster_failed=%d reveal_ms=%.1f reason=%s",
            str((self._deck or {}).get("deck_id") or ""),
            self._deck_build_ms,
            self._deck_prepare_total,
            self._deck_prepare_cache_hits,
            self._deck_prepare_ready,
            self._deck_prepare_failed,
            reveal_ms,
            reason,
        )

    def _on_poster_prefetch_batch_finished(
        self,
        batch_id: int,
        ready: int,
        failed: int,
        total: int,
        cache_hits: int,
    ) -> None:
        if batch_id != self._deck_prepare_batch_id:
            return
        self._poster_prefetch_failed = max(0, int(failed))
        all_settled_ms = (
            (perf_counter() - self._deck_prepare_started_at) * 1000.0
            if self._deck_prepare_started_at > 0.0
            else 0.0
        )
        logger.info(
            "recommendation posters settled deck_id=%s poster_total=%d "
            "poster_cache_hits=%d poster_ready=%d poster_failed=%d "
            "all_posters_settled_ms=%.1f",
            str((self._deck or {}).get("deck_id") or ""),
            max(0, int(total)),
            max(0, int(cache_hits)),
            max(0, int(ready)),
            self._poster_prefetch_failed,
            all_settled_ms,
        )
        if self._deck is not None:
            self._update_deck_status()

    def _present_recommendation_deck(
        self,
        deck: dict,
        *,
        prepare_posters: bool = False,
    ) -> None:
        self._deck = deck
        self._deck_dirty = False
        self._deck_build_in_progress = False
        self._deck_build_failed = False
        active_limit = max(0, int(deck.get("active_limit") or ACTIVE_DECK_SIZE))
        self._all_candidates = list(deck.get("active") or [])[:active_limit]
        self._pool_unique_total = len(self._all_candidates)
        self._detail_entries = {}
        self._search_index = build_candidate_search_index(self._all_candidates)
        restored_selection = str(deck.get("last_selected_pool_key") or "")
        if restored_selection and any(
            candidate_detail_identity(candidate) == restored_selection
            for candidate in self._all_candidates
        ):
            self._selected_identity = restored_selection
        self._update_deck_status()
        self._poster_prefetch.allow_failed_retries()
        if prepare_posters:
            self._deck_prepare_priority_identities = {
                candidate_detail_identity(candidate)
                for candidate in self._all_candidates[:POSTER_PRIORITY_COUNT]
            }
            self._poster_prefetch.start_batch(
                self._all_candidates,
                data_language=self._data_language,
                priority_count=POSTER_PRIORITY_COUNT,
            )
        else:
            self._poster_prefetch.enqueue_candidates(
                self._all_candidates,
                data_language=self._data_language,
            )
        self._apply_visible_candidates()
        if not self._all_candidates:
            self._clear_detail(show_filters_hint=False)
        self._update_deck_reserve_indicator()

    def _maybe_request_recommendation_refill(self) -> None:
        deck = self._deck or {}
        if deck.get("refill_needed") is not True or self._on_refill_needed is None:
            return
        deck_id = str(deck.get("deck_id") or "")
        if deck_id and deck_id in self._refill_requested_deck_ids:
            return
        last_attempt = getattr(self, "_refill_last_attempt", None)
        if (
            deck_id
            and isinstance(last_attempt, tuple)
            and len(last_attempt) == 2
            and last_attempt[0] == deck_id
            and perf_counter() - float(last_attempt[1]) < REFILL_RETRY_COOLDOWN_SECONDS
        ):
            return
        try:
            self._on_refill_needed(self._deck_preferences())
        except Exception:
            logger.exception("recommendation refill request failed")
            return
        if deck_id:
            self._refill_requested_deck_ids = {deck_id}
            self._refill_last_attempt = (deck_id, perf_counter())
        if deck.get("underfilled_reason") in {"no_eligible_candidates", "active_underfilled", "reserve_exhausted"}:
            self._deck_status_label.setText(tr("recommendations.state.replenishing"))
            self._deck_replenishing_active = True
        self._update_deck_reserve_indicator()

    def _load_recommendation_deck(self, *, force_new: bool) -> None:
        if not self._recommendations_active:
            self._deck_dirty = True
            return
        previous_deck = self._deck
        previous_deck_id = str((previous_deck or {}).get("deck_id") or "")
        previous_preferences = dict((previous_deck or {}).get("candidate_filters") or (previous_deck or {}).get("preferences") or {})
        previous_vector = dict((previous_deck or {}).get("recommendation_vector") or {})
        self._new_deck_button.setEnabled(False)
        self._deck_build_in_progress = True
        self._deck_build_failed = False
        self._deck_status_label.setText(tr("recommendations.state.loading"))
        self._deck_status_label.show()
        self._update_deck_reserve_indicator()
        build_started = perf_counter()
        try:
            try:
                deck = self._deck_service.refresh_deck(
                    self._deck_preferences(),
                    datetime.now(timezone.utc),
                    vector=self._deck_vector(),
                    variation_seed=self._session.variation_seed,
                    force_new=force_new,
                )
            except TypeError as error:
                if "unexpected keyword argument" not in str(error):
                    raise
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
            self._deck_status_label.hide()
            self._clear_detail(show_filters_hint=False, error=True)
            self._deck_build_in_progress = False
            self._deck_build_failed = True
            self._show_deck_content()
            self._update_deck_reserve_indicator()
            return
        finally:
            self._new_deck_button.setEnabled(True)

        self._deck_build_ms = (perf_counter() - build_started) * 1000.0
        current_deck_id = str(deck.get("deck_id") or "")
        current_preferences = dict(deck.get("candidate_filters") or deck.get("preferences") or self._deck_preferences())
        current_vector = dict(deck.get("recommendation_vector") or self._deck_vector())
        vector_only_remix = (
            not force_new
            and previous_deck is not None
            and current_preferences == previous_preferences
            and (
                current_vector != previous_vector
                or int(deck.get("variation_seed") or 0)
                != int(previous_deck.get("variation_seed") or 0)
            )
        )
        replacement = (
            force_new
            or previous_deck is None
            or current_deck_id != previous_deck_id
            or current_preferences != previous_preferences
            or current_vector != previous_vector
        )
        if replacement:
            self._begin_deck_preparation()
        logger.info(
            "recommendation deck built deck_id=%s deck_build_ms=%.1f active=%d reserve=%d replacement=%s",
            current_deck_id,
            self._deck_build_ms,
            len(deck.get("active") or []),
            len(deck.get("reserve") or []),
            replacement,
        )
        self._present_recommendation_deck(
            deck,
            prepare_posters=replacement and not vector_only_remix,
        )
        self._initial_deck_loaded = True
        self._maybe_request_recommendation_refill()

    def _on_new_deck_clicked(self) -> None:
        self._session.variation_seed += 1
        self._load_recommendation_deck(force_new=True)

    def _apply_recommendation_action(self, action: str, *, user_score: int | None = None) -> None:
        candidate = self._selected_candidate
        deck = self._deck
        if not isinstance(candidate, dict) or not isinstance(deck, dict):
            return
        current_row = self._results_list.currentIndex().row()
        try:
            action_kwargs = {"user_score": user_score} if user_score is not None else {}
            updated = self._deck_service.apply_action_and_refill(
                str(deck["deck_id"]),
                candidate,
                action,
                **action_kwargs,
            )
        except Exception:
            logger.exception("recommendation action failed: %s", action)
            self._deck_status_label.setText(tr("recommendations.action.failed"))
            self._deck_status_label.show()
            return

        top_up = getattr(self._deck_service, "top_up_deck", None)
        if updated.get("refill_needed") is True and callable(top_up):
            try:
                updated = top_up(
                    str(updated["deck_id"]),
                    datetime.now(timezone.utc),
                )
            except Exception:
                logger.exception("local recommendation deck top-up failed")
        self._selected_candidate = None
        self._selected_identity = None
        self._candidate_rating_selector.clear()
        self._present_recommendation_deck(updated)
        if self._candidates:
            row = min(max(0, current_row), len(self._candidates) - 1)
            self._results_list.setCurrentIndex(self._model.index(row, 0))
        else:
            self._clear_detail(show_filters_hint=False)
        self._update_deck_status()
        self._maybe_request_recommendation_refill()
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
            top_up = getattr(self._deck_service, "top_up_deck", None)
            deck = self._deck
            if (
                isinstance(deck, dict)
                and dict(deck.get("candidate_filters") or deck.get("preferences") or {}) == self._deck_preferences()
                and dict(deck.get("recommendation_vector") or {}) == self._deck_vector()
                and callable(top_up)
            ):
                try:
                    updated = top_up(
                        str(deck["deck_id"]),
                        datetime.now(timezone.utc),
                    )
                except Exception:
                    logger.exception("recommendation deck refresh top-up failed")
                    self._load_recommendation_deck(force_new=False)
                else:
                    first_candidates_after_empty_deck = (
                        len(deck.get("active") or []) == 0
                        and len(updated.get("active") or []) > 0
                    )
                    if first_candidates_after_empty_deck:
                        self._begin_deck_preparation()
                    self._present_recommendation_deck(
                        updated,
                        prepare_posters=first_candidates_after_empty_deck,
                    )
                    self._maybe_request_recommendation_refill()
            else:
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
        record_reveal = getattr(self._deck_service, "record_detail_reveal", None)
        if self._deck is not None and callable(record_reveal):
            try:
                record_reveal(
                    str(self._deck.get("deck_id") or ""),
                    candidate,
                )
            except (OSError, ValueError, KeyError):
                logger.exception("could not persist recommendation detail reveal")
        lookup_done = perf_counter()

        identity = candidate_detail_identity(candidate)
        self._poster_request_seq += 1
        request_seq = self._poster_request_seq
        entry = self._detail_entries.get(identity)
        if entry is None:
            entry = self._build_detail_entry(candidate)
            self._detail_entries[identity] = entry
        build_done = perf_counter()

        self._hide_workspace_state()
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
        if any(worker.isRunning() for worker in self._localized_poster_workers):
            self._pending_localized_poster = (dict(candidate), identity, request_seq)
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
        pending = getattr(self, "_pending_localized_poster", None)
        self._pending_localized_poster = None
        if pending is not None and pending[1] == self._selected_identity:
            candidate, identity, request_seq = pending
            self._start_localized_poster_enrichment(candidate, identity, request_seq)

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
            self._deck_status_label.setText(tr("recommendations.state.replenishing"))
            self._deck_status_label.hide()
            self._clear_detail(show_filters_hint=False, loading=True)
        else:
            self._deck_replenishing_active = False
        self._update_deck_reserve_indicator()
        if not self._session.is_loading and self._recommendations_active and self._deck_dirty:
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
        error: bool = False,
    ) -> None:
        self._poster_request_seq += 1
        self._detail_scroll.hide()
        self._reset_detail_scroll()
        self._set_action_panel_enabled(False)
        if loading:
            state = "loading"
        elif error or (self._session.last_error and len(self._candidates) == 0):
            state = "error"
        elif show_filters_hint:
            state = "idle"
        elif search_active:
            state = "no_results"
        elif len(self._candidates) == 0:
            deck = self._deck if isinstance(self._deck, dict) else {}
            excluded = deck.get("excluded") if isinstance(deck.get("excluded"), dict) else {}
            pool_total = int(excluded.get("pool_total") or 0)
            state = "pool_empty" if pool_total == 0 and not deck.get("last_action") else "no_results"
        else:
            state = "idle"
        if len(self._candidates) == 0 or state in {"loading", "error"}:
            self._deck_status_label.hide()
        self._show_workspace_state(state)
