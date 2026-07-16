from __future__ import annotations

from copy import deepcopy

import pytest
from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QWidget,
)

from desktop.candidates.list_model import CandidateListModel, CandidateListRoles
from desktop.candidates.empty_state import RecommendationEmptyState
from desktop.candidates.filters_view import CandidateFiltersView
from desktop.candidates.list_view import CandidateListView
from desktop.candidates.presenters import candidate_detail_identity
from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS


def _searchable_candidate() -> dict:
    return {
        "pool_entry_key": "searchable-only|2024",
        "title": "Searchable Only",
        "year": 2024,
        "is_searchable": True,
        "is_complete": False,
        "tmdb_score": None,
        "tmdb_votes": None,
        "final_score": None,
        "overview": "Can be searched before prediction data is ready.",
    }


def _predict_ready_candidate() -> dict:
    return {
        "pool_entry_key": "predict-ready|2023",
        "title": "Predict Ready",
        "year": 2023,
        "is_searchable": True,
        "is_complete": True,
        "tmdb_score": 8.1,
        "tmdb_votes": 10000,
        "final_score": 8.0,
        "overview": "Has enough scores for prediction-ready mode.",
    }


class FakeCandidateService:
    SEARCH_SORT_MODES = (
        "final_score",
        "quality_score",
        "tmdb_score",
        "tmdb_votes",
        "tmdb_popularity",
        "year",
        "text_relevance",
        "relevance",
    )
    SEARCH_SORT_MODE_LABELS = {
        "final_score": "Итог",
        "quality_score": "Качество",
        "tmdb_score": "TMDb",
        "tmdb_votes": "Голоса TMDb",
        "tmdb_popularity": "Популярность TMDb",
        "year": "Год",
        "text_relevance": "Текст",
        "relevance": "Релевантность",
    }

    def __init__(self, candidates: list[dict] | None = None) -> None:
        self.candidates = deepcopy(candidates or [_searchable_candidate(), _predict_ready_candidate()])
        self.hidden_candidates: list[dict] = []
        self.applied_filters: list[dict] = []
        self.applied_text_queries: list[str] = []
        self.overview_calls = 0
        self.chip_options = {"genres": [], "countries": []}
        self._fts_enabled = False

    def is_fts_search_enabled(self) -> bool:
        return self._fts_enabled

    def set_fts_enabled(self, enabled: bool) -> None:
        self._fts_enabled = bool(enabled)

    def get_search_overview_view(self) -> dict:
        self.overview_calls += 1
        return {
            "is_empty": len(self.candidates) == 0,
            "summary": f"{len(self.candidates)} candidates",
            "stats": self.get_pool_stats_view()["stats"],
            "candidates": deepcopy(self.candidates),
        }

    def search_candidate_pool(self, candidates: list[dict], filters: dict) -> dict:
        self.applied_filters.append(dict(filters))
        hidden = {candidate_detail_identity(candidate) for candidate in self.hidden_candidates}
        filtered = []
        for candidate in candidates:
            if candidate.get("is_searchable") is not True:
                continue
            if filters.get("media_type") and candidate.get("media_type") != filters.get("media_type"):
                continue
            if filters.get("hide_hidden") and candidate_detail_identity(candidate) in hidden:
                continue
            if filters.get("only_complete") and candidate.get("is_complete") is not True:
                continue
            filtered.append(candidate)
        return {"candidates": filtered, "filtered_count": len(filtered)}

    def search_candidate_pool_text(self, candidates: list[dict], filters: dict, *, text_query: str | None = None) -> dict:
        self.applied_text_queries.append(str(text_query or ""))
        normalized = str(text_query or "").strip().casefold()
        view = self.search_candidate_pool(candidates, filters)
        if normalized == "" or not self._fts_enabled:
            return view
        filtered = [
            candidate
            for candidate in view["candidates"]
            if normalized in str(candidate.get("title") or "").casefold()
        ]
        enriched = []
        for candidate in filtered:
            payload = dict(candidate)
            payload["text_relevance_score"] = 0.8
            payload["combined_relevance_score"] = 0.7
            payload["matched_fields"] = ["title"]
            enriched.append(payload)
        return {"candidates": enriched, "filtered_count": len(enriched), "fts_enabled": True}

    def sort_search_candidates(self, candidates: list[dict], sort_mode: str) -> dict:
        return {
            "candidates": sorted(list(candidates), key=lambda item: item.get("title") or ""),
            "sort_mode": sort_mode,
            "hidden_duplicates": 0,
        }

    def get_pool_stats_view(self) -> dict:
        total = len(self.candidates)
        ready = sum(1 for candidate in self.candidates if candidate.get("is_complete") is True)
        return {
            "summary": f"{total} candidates",
            "stats": {
                "unique_total": total,
                "storage_total": total,
                "ready_total": ready,
                "incomplete_total": total - ready,
            },
        }

    def get_search_filter_defaults_view(self) -> dict:
        return {"defaults": dict(DEFAULT_BROWSE_FILTERS)}

    def get_search_filter_chip_options_view(self) -> dict:
        return deepcopy(self.chip_options)

    def hide_candidate(self, candidate: dict) -> dict:
        self.hidden_candidates.append(deepcopy(candidate))
        return {"ok": True, "hidden": True}


class FakeRecommendationDeckService:
    def __init__(self, service: FakeCandidateService) -> None:
        self.service = service
        self.deck_id = "test-deck"
        self.action_calls: list[tuple[str, str, int | None]] = []
        self._deck: dict = {}

    def refresh_deck(self, preferences: dict, _now, *, force_new: bool = False) -> dict:
        view = self.service.search_candidate_pool(deepcopy(self.service.candidates), preferences)
        candidates = self.service.sort_search_candidates(view["candidates"], "final_score")["candidates"]
        self._deck = {
            "deck_id": self.deck_id,
            "active": candidates[:25],
            "reserve": candidates[25:95],
            "active_limit": 25,
            "reserve_size": 70,
            "underfilled_reason": "active_underfilled" if len(candidates) < 25 else None,
        }
        return deepcopy(self._deck)

    def apply_action_and_refill(
        self, deck_id: str, candidate: dict, action: str, *, user_score: int | None = None
    ) -> dict:
        assert deck_id == self.deck_id
        identity = candidate_detail_identity(candidate)
        self.action_calls.append((action, identity, user_score))
        if action == "hidden":
            self.service.hide_candidate(candidate)
        self._deck["active"] = [
            item for item in self._deck["active"] if candidate_detail_identity(item) != identity
        ]
        promoted = self._deck["reserve"].pop(0) if self._deck["reserve"] else None
        if promoted is not None:
            self._deck["active"].append(promoted)
        self._deck["last_action"] = {
            "action": action,
            "transition": {"ok": True, "state": action},
        }
        return deepcopy(self._deck)


def _build_views(
    qtbot,
    service: FakeCandidateService | None = None,
    deck_service: FakeRecommendationDeckService | None = None,
):
    from desktop.theme.shell_layout import CANDIDATE_DETAIL_COLLAPSE_WIDTH_PX

    service = service or FakeCandidateService()
    deck_service = deck_service or FakeRecommendationDeckService(service)
    session = CandidateSearchSession(service=service)
    filters_view = CandidateFiltersView(session, service=service)
    filters_view._form.advanced_mode_toggle.setChecked(True)
    list_view = CandidateListView(session, service=service, deck_service=deck_service)
    list_widget = list_view.widget.findChild(QListView, "candidateListWidget")
    assert list_widget is not None
    list_widget.setUpdatesEnabled(False)
    qtbot.addWidget(filters_view.widget)
    qtbot.addWidget(list_view.widget)
    filters_view.widget.show()
    list_view.widget.resize(1280, 800)
    list_view.widget.show()
    list_view.on_tab_activated()
    qtbot.waitUntil(lambda: list_view._deck is not None)
    qtbot.waitUntil(
        lambda: list_view.widget.findChild(QStackedWidget, "recommendationsDeckStack").currentWidget()
        is list_view._deck_content_page
    )
    return service, session, filters_view, list_view


def _candidate_list(list_view: CandidateListView) -> QListView:
    widget = list_view.widget.findChild(QListView, "candidateListWidget")
    assert widget is not None
    return widget


def _listed_titles(list_widget: QListView) -> list[str]:
    titles = []
    model = list_widget.model()
    for row in range(model.rowCount()):
        candidate = model.data(model.index(row, 0), CandidateListRoles.CandidateRole)
        titles.append(candidate.get("title"))
    return titles


def _listed_count(list_widget: QListView) -> int:
    return list_widget.model().rowCount()


def _candidate_set(count: int, *, long_overview: bool = False) -> list[dict]:
    return [
        {
            **_predict_ready_candidate(),
            "pool_entry_key": f"recommendation-{index}|2024|movie",
            "title": f"Recommendation {index:03d}",
            "overview": ("A detailed recommendation overview. " * 120) if long_overview else "Overview.",
        }
        for index in range(count)
    ]


def test_recommendations_screen_displays_at_most_twenty_five_items(qtbot) -> None:
    service = FakeCandidateService(_candidate_set(45))
    _service, _session, _filters_view, list_view = _build_views(qtbot, service)

    assert _listed_count(_candidate_list(list_view)) == 25


def test_recommendations_hide_detail_panel_in_compact_layout(qtbot) -> None:
    from desktop.theme.shell_layout import (
        CANDIDATE_DETAIL_COLLAPSE_WIDTH_PX,
        CANDIDATE_LIST_MAX_WIDTH_PX,
    )

    service = FakeCandidateService(_candidate_set(2))
    _service, _session, _filters_view, list_view = _build_views(qtbot, service)
    for compact in (True, False, True, False):
        width = (
            CANDIDATE_DETAIL_COLLAPSE_WIDTH_PX - 1
            if compact
            else 1280
        )
        list_view.widget.resize(width, 800)

        qtbot.waitUntil(lambda: list_view._is_compact_layout is compact)
        assert list_view._detail_panel.isHidden() is compact
        assert list_view._splitter.handle(1).isHidden() is compact
        if compact:
            assert list_view._list_panel.width() >= list_view._splitter.width() - 1
        else:
            assert list_view._detail_panel.isVisible()
            assert list_view._list_panel.maximumWidth() == CANDIDATE_LIST_MAX_WIDTH_PX


@pytest.mark.parametrize(
    ("button_name", "expected_action"),
    [
        ("recommendationWatchlistButton", "watchlist"),
        ("recommendationHiddenButton", "hidden"),
    ],
)
def test_recommendation_actions_use_deck_state_transition(
    qtbot,
    button_name: str,
    expected_action: str,
) -> None:
    service = FakeCandidateService(_candidate_set(2))
    deck_service = FakeRecommendationDeckService(service)
    _service, _session, _filters_view, list_view = _build_views(qtbot, service, deck_service)
    list_widget = _candidate_list(list_view)
    list_widget.setCurrentIndex(list_widget.model().index(0, 0))
    button = list_view.widget.findChild(QPushButton, button_name)

    assert button is not None
    qtbot.waitUntil(button.isVisible)
    assert button.isEnabled()
    detail_scroll = list_view.widget.findChild(QScrollArea, "candidateSearchDetailScroll")
    assert detail_scroll is not None
    detail_scroll.ensureWidgetVisible(button)
    qtbot.wait(10)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: bool(deck_service.action_calls))
    assert deck_service.action_calls[0][0] == expected_action
    assert _listed_count(list_widget) == 1
    assert list_view._deck_stack.currentWidget() is list_view._deck_content_page


def test_recommendation_watched_action_uses_selected_reaction(qtbot) -> None:
    from desktop.shared.widgets.user_rating_selector import UserRatingSelector

    service = FakeCandidateService(_candidate_set(2))
    deck_service = FakeRecommendationDeckService(service)
    _service, _session, _filters_view, list_view = _build_views(qtbot, service, deck_service)
    list_widget = _candidate_list(list_view)
    list_widget.setCurrentIndex(list_widget.model().index(0, 0))
    selector = list_view.widget.findChild(UserRatingSelector, "recommendationUserRatingSelector")

    assert selector is not None and selector.isEnabled()
    qtbot.mouseClick(selector.buttons()[0], Qt.MouseButton.LeftButton)

    assert deck_service.action_calls[0][0] == "watched"
    assert deck_service.action_calls[0][2] == 1


def test_recommendation_action_promotes_reserve_item(qtbot) -> None:
    service = FakeCandidateService(_candidate_set(31))
    deck_service = FakeRecommendationDeckService(service)
    _service, _session, _filters_view, list_view = _build_views(qtbot, service, deck_service)
    list_widget = _candidate_list(list_view)
    initial_titles = set(_listed_titles(list_widget))
    list_widget.setCurrentIndex(list_widget.model().index(0, 0))
    button = list_view.widget.findChild(QPushButton, "recommendationHiddenButton")

    assert button is not None
    qtbot.waitUntil(button.isVisible)
    detail_scroll = list_view.widget.findChild(QScrollArea, "candidateSearchDetailScroll")
    assert detail_scroll is not None
    detail_scroll.ensureWidgetVisible(button)
    qtbot.wait(10)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    updated_titles = set(_listed_titles(list_widget))
    assert _listed_count(list_widget) == 25
    assert updated_titles - initial_titles == {"Recommendation 025"}
    current_row = list_widget.currentIndex().row()
    assert list_view._selected_candidate == list_view._candidates[current_row]
    assert list_view._selected_identity == candidate_detail_identity(
        list_view._candidates[current_row]
    )


def test_rapid_repeated_recommendation_action_is_applied_once(qtbot) -> None:
    service = FakeCandidateService(_candidate_set(31))
    deck_service = FakeRecommendationDeckService(service)
    _service, _session, _filters_view, list_view = _build_views(qtbot, service, deck_service)
    listing = _candidate_list(list_view)
    listing.setCurrentIndex(listing.model().index(0, 0))

    list_view._apply_recommendation_action("hidden")
    list_view._apply_recommendation_action("hidden")

    assert len(deck_service.action_calls) == 1
    assert list_view._hidden_action_button.isEnabled() is False
    qtbot.waitUntil(lambda: list_view._hidden_action_button.isEnabled())


def test_empty_recommendation_deck_shows_stable_empty_state(qtbot) -> None:
    from desktop.i18n import tr

    service = FakeCandidateService([])
    service.candidates = []
    _service, _session, _filters_view, list_view = _build_views(qtbot, service)
    status = list_view.widget.findChild(QLabel, "recommendationsDeckStatus")

    assert _listed_count(_candidate_list(list_view)) == 0
    assert status is not None and status.isHidden()
    assert list_view._workspace_state.state == "pool_empty"
    assert list_view._workspace_state.title_label.text() == tr(
        "recommendations.empty_state.pool_empty.title"
    )
    assert list_view._workspace_state.isVisible()
    assert list_view._detail_panel.isAncestorOf(list_view._workspace_state)
    assert list_view.widget.findChild(QFrame, "recommendationActionPanel").isHidden()


def test_recommendation_header_keeps_status_and_reserve_controls_in_bounds(qtbot) -> None:
    service = FakeCandidateService(_candidate_set(31))
    deck_service = FakeRecommendationDeckService(service)
    _service, _session, _filters_view, list_view = _build_views(
        qtbot, service, deck_service
    )
    header = list_view.widget.findChild(QWidget, "recommendationsFeedHeader")
    title = list_view.widget.findChild(QLabel, "recommendationsFeedTitle")
    reserve = list_view.widget.findChild(QLabel, "recommendationsDeckReserveLabel")
    status = list_view.widget.findChild(QLabel, "recommendationsDeckStatus")
    retry = list_view.widget.findChild(QPushButton, "recommendationsDeckRefillButton")
    assert header is not None and title is not None and reserve is not None
    assert status is not None and retry is not None

    status.setText("25 рекомендаций")
    status.show()
    retry.setText("Повторить")
    retry.show()
    list_view.widget.resize(1280, 800)
    qtbot.wait(50)

    assert status.y() == title.y()
    assert reserve.y() > title.y()
    assert status.geometry().right() <= header.contentsRect().right()
    assert retry.geometry().right() <= header.contentsRect().right()


def test_compact_recommendations_show_visible_loading_state(qtbot) -> None:
    from desktop.i18n import tr

    service = FakeCandidateService([])
    service.candidates = []
    _service, session, _filters_view, list_view = _build_views(qtbot, service)
    list_view.widget.resize(900, 700)
    qtbot.waitUntil(lambda: list_view._is_compact_layout is True)

    session._set_loading(True)

    assert list_view._deck_status_label.isHidden()
    assert list_view._active_workspace_state == "loading"
    assert list_view._list_body_stack.currentWidget() is list_view._compact_workspace_state
    assert list_view._compact_workspace_state.isVisible()
    assert list_view._compact_workspace_state.title_label.text() == tr(
        "recommendations.empty_state.loading.title"
    )
    assert list_view._decision_cluster.isHidden()


def test_compact_recommendations_keep_non_empty_list_without_selection(qtbot) -> None:
    _service, _session, _filters_view, list_view = _build_views(qtbot)
    list_view.widget.resize(900, 700)
    qtbot.waitUntil(lambda: list_view._is_compact_layout)

    list_view._results_list.clearSelection()
    list_view._results_list.setCurrentIndex(QModelIndex())
    list_view._clear_detail(show_filters_hint=False)

    assert list_view._candidates
    assert list_view._active_workspace_state == "idle"
    assert list_view._list_body_stack.currentWidget() is list_view._results_list
    assert list_view._results_list.isVisible()


def test_recommendation_workspace_uses_no_results_and_hides_for_card(qtbot) -> None:
    from desktop.i18n import tr

    _service, _session, _filters_view, list_view = _build_views(qtbot)
    list_view._search_input.setText("definitely missing")
    list_view._apply_visible_candidates()

    assert list_view._workspace_state.state == "no_results"
    assert list_view._workspace_state.title_label.text() == tr(
        "recommendations.empty_state.no_results.title"
    )
    assert list_view._deck_status_label.isHidden()

    list_view._search_input.clear()
    list_view._apply_visible_candidates()
    listing = _candidate_list(list_view)
    listing.setCurrentIndex(listing.model().index(0, 0))

    assert list_view._active_workspace_state is None
    assert list_view._workspace_state.isHidden()
    assert list_view._detail_scroll.isVisible()


def test_recommendation_deck_error_uses_non_modal_workspace_state(qtbot) -> None:
    from desktop.i18n import tr

    class ErrorDeckService:
        def refresh_deck(self, *_args, **_kwargs):
            raise RuntimeError("network unavailable")

    service = FakeCandidateService([])
    service.candidates = []
    session = CandidateSearchSession(service=service)
    list_view = CandidateListView(session, service=service, deck_service=ErrorDeckService())
    qtbot.addWidget(list_view.widget)
    list_view.widget.resize(1280, 800)
    list_view.widget.show()
    list_view.on_tab_activated()
    qtbot.waitUntil(lambda: list_view._active_workspace_state == "error")

    assert list_view._workspace_state.isVisible()
    assert list_view._workspace_state.title_label.text() == tr(
        "recommendations.empty_state.error.title"
    )
    assert list_view._deck_status_label.isHidden()
    assert list_view._deck_refill_button.isVisible()
    assert list_view._deck_refill_button.text() == tr("recommendations.deck_reserve.retry")


def test_filter_replenish_lifecycle_updates_empty_recommendation_workspace(qtbot) -> None:
    service = FakeCandidateService([])
    service.candidates = []
    _service, _session, _filters_view, list_view = _build_views(qtbot, service)

    list_view.on_replenish_state_changed("loading")
    assert list_view._active_workspace_state == "loading"

    list_view.on_replenish_state_changed("error")
    assert list_view._active_workspace_state == "error"
    assert list_view._deck_stack.currentWidget() is list_view._deck_content_page

    list_view._deck = {"active": [], "reserve": [], "excluded": {"pool_total": 0}}
    list_view.on_replenish_state_changed("finished")
    assert list_view._active_workspace_state == "pool_empty"


def test_recommendation_empty_state_accepts_custom_presentation(qtbot) -> None:
    state = RecommendationEmptyState(
        "idle",
        title="Custom title",
        subtitle="Custom subtitle",
        icon="search",
        compact=True,
    )
    qtbot.addWidget(state)

    assert state.state == "idle"
    assert state.title_label.text() == "Custom title"
    assert state.subtitle_label.text() == "Custom subtitle"
    assert state._icon_label.pixmap().isNull() is False


def test_recommendation_copy_is_available_in_ru_and_en() -> None:
    from desktop.i18n import translate

    keys = (
        "tabs.candidates",
        "recommendations.feed.title",
        "recommendations.feed.count",
        "recommendations.preparing.title",
        "recommendations.preparing.detail",
        "recommendations.preparing.progress",
        "recommendations.empty_state.loading.title",
        "recommendations.empty_state.loading.subtitle",
        "recommendations.empty_state.pool_empty.title",
        "recommendations.empty_state.pool_empty.subtitle",
        "recommendations.empty_state.no_results.title",
        "recommendations.empty_state.no_results.subtitle",
        "recommendations.empty_state.error.title",
        "recommendations.empty_state.error.subtitle",
        "recommendations.empty_state.idle.title",
        "recommendations.empty_state.idle.subtitle",
        "recommendations.new_deck",
        "recommendations.reasons.title",
        "recommendations.action.watched",
        "recommendations.action.watchlist",
        "recommendations.action.hidden",
        "recommendations.state.empty",
    )
    for language in ("ru", "en"):
        assert all(translate(key, interface_language=language) != key for key in keys)


def test_recommendation_actions_live_below_main_info_inside_scroll(qtbot) -> None:
    from desktop.theme.shell_layout import LEFT_PANEL_TOP_COMPENSATION_PX

    service = FakeCandidateService(_candidate_set(1, long_overview=True))
    _service, _session, _filters_view, list_view = _build_views(qtbot, service)
    list_view.widget.resize(1280, 720)
    list_widget = _candidate_list(list_view)
    list_widget.setCurrentIndex(list_widget.model().index(0, 0))
    qtbot.wait(10)
    panel = list_view.widget.findChild(QFrame, "recommendationActionPanel")
    reasons_panel = list_view.widget.findChild(QFrame, "recommendationReasonsPanel")
    decision_cluster = list_view.widget.findChild(QWidget, "recommendationDecisionCluster")
    detail_scroll = list_view.widget.findChild(QScrollArea, "candidateSearchDetailScroll")
    main_info_panel = list_view.widget.findChild(QFrame, "detailMainInfoPanel")
    overview_section = list_view.widget.findChild(QFrame, "detailOverviewSection")
    overview_footer = list_view.widget.findChild(QWidget, "detailOverviewFooter")
    overview_text = list_view.widget.findChild(QLabel, "detailOverviewText")
    watchlist_button = list_view.widget.findChild(QPushButton, "recommendationWatchlistButton")
    hidden_button = list_view.widget.findChild(QPushButton, "recommendationHiddenButton")
    rating_buttons = list(list_view._candidate_rating_selector.buttons())

    assert panel is not None and panel.isVisible()
    assert reasons_panel is not None and reasons_panel.isVisible()
    assert decision_cluster is not None and decision_cluster.isVisible()
    assert detail_scroll is not None
    assert main_info_panel is not None
    assert overview_section is not None and overview_section.isVisible()
    assert overview_footer is not None and overview_footer.isVisible()
    assert overview_text is not None and overview_text.isVisible()
    assert detail_scroll.widget().isAncestorOf(panel)
    assert panel.parentWidget() is decision_cluster
    assert reasons_panel.parentWidget() is overview_footer
    assert overview_footer.parentWidget() is overview_section
    assert overview_text.geometry().bottom() <= overview_footer.geometry().top()
    assert decision_cluster.layout().count() == 1
    assert decision_cluster.parentWidget().objectName() == "detailMainInfoSection"
    assert decision_cluster.geometry().top() >= main_info_panel.geometry().bottom()
    assert list_view._detail_panel.layout().contentsMargins().top() == LEFT_PANEL_TOP_COMPENSATION_PX
    rating_widths = [button.width() for button in rating_buttons]
    assert max(rating_widths) - min(rating_widths) <= 1
    assert len({button.height() for button in rating_buttons}) == 1
    assert watchlist_button is not None and hidden_button is not None
    assert watchlist_button.size() == hidden_button.size()
    assert detail_scroll.verticalScrollBar().maximum() > 0


def test_recommendation_reason_remains_visible_without_overview(qtbot) -> None:
    from PyQt6.QtCore import QPoint

    candidates = _candidate_set(1)
    candidates[0]["overview"] = ""
    service = FakeCandidateService(candidates)
    _service, _session, _filters_view, list_view = _build_views(qtbot, service)
    list_view.widget.resize(1280, 720)
    list_widget = _candidate_list(list_view)
    list_widget.setCurrentIndex(list_widget.model().index(0, 0))
    qtbot.wait(10)

    overview_section = list_view.widget.findChild(QFrame, "detailOverviewSection")
    overview_title = list_view.widget.findChild(QLabel, "detailOverviewHeader")
    overview_text = list_view.widget.findChild(QLabel, "detailOverviewText")
    reasons_panel = list_view.widget.findChild(QFrame, "recommendationReasonsPanel")

    assert overview_section is not None and overview_section.isVisible()
    assert overview_title is not None and overview_title.isHidden()
    assert overview_text is not None and overview_text.isHidden()
    assert reasons_panel is not None and reasons_panel.isVisible()
    assert reasons_panel.mapTo(overview_section, QPoint(0, 0)).y() <= 1


def test_recommendation_reason_label_replaces_previous_intent(qtbot) -> None:
    candidates = _candidate_set(2)
    candidates[0].update({"year": 2010, "tmdb_popularity": 90, "tmdb_score": None})
    candidates[1].update({"year": 2011, "tmdb_popularity": 8, "tmdb_score": None})
    service = FakeCandidateService(candidates)
    _service, session, _filters_view, list_view = _build_views(qtbot, service)
    list_widget = _candidate_list(list_view)

    session.set_recommendation_vector(
        {"mood": "any", "rarity_level": 0, "diversity_level": 2, "openness_level": 2}
    )
    list_widget.setCurrentIndex(list_widget.model().index(0, 0))
    qtbot.wait(10)
    first_text = list_view._reason_label.text()

    session.set_recommendation_vector(
        {"mood": "any", "rarity_level": 4, "diversity_level": 2, "openness_level": 2}
    )
    list_widget.setCurrentIndex(list_widget.model().index(1, 0))
    qtbot.wait(10)
    second_text = list_view._reason_label.text()

    assert "Популярный выбор" in first_text
    assert "Менее известный выбор" in second_text
    assert "Популярный выбор" not in second_text
    assert all(line.strip("• ") for line in second_text.splitlines())
    assert len(second_text.splitlines()) == len(set(second_text.splitlines()))


def test_settings_tab_does_not_overlap_recommendation_poster(qtbot) -> None:
    from PyQt6.QtCore import QPoint, QRect
    from PyQt6.QtWidgets import QTabWidget

    from desktop.theme import build_app_style

    service = FakeCandidateService(_candidate_set(1))
    session = CandidateSearchSession(service=service)
    list_view = CandidateListView(
        session,
        service=service,
        deck_service=FakeRecommendationDeckService(service),
    )
    list_view._results_list.setUpdatesEnabled(False)
    tabs = QTabWidget()
    tabs.setObjectName("mainTabs")
    tabs.setStyleSheet(build_app_style())
    tabs.addTab(list_view.widget, "Recommendations")
    tabs.addTab(QWidget(), "Collection")
    tabs.addTab(QWidget(), "Search")
    settings_index = tabs.addTab(QWidget(), "Settings")
    qtbot.addWidget(tabs)
    tabs.resize(1280, 720)
    tabs.show()
    list_view.on_tab_activated()
    qtbot.waitUntil(lambda: list_view._deck is not None)
    qtbot.waitUntil(
        lambda: list_view._deck_stack.currentWidget() is list_view._deck_content_page
    )

    list_widget = _candidate_list(list_view)
    list_widget.setCurrentIndex(list_widget.model().index(0, 0))
    qtbot.wait(10)

    tab_bar = tabs.tabBar()
    settings_rect = tab_bar.tabRect(settings_index)
    settings_rect = QRect(
        tab_bar.mapTo(tabs, settings_rect.topLeft()),
        settings_rect.size(),
    )
    poster = list_view._detail_card._poster_shell
    poster_rect = QRect(poster.mapTo(tabs, QPoint(0, 0)), poster.size())

    assert settings_rect.intersects(poster_rect) is False


def test_filters_view_reload_filter_options_uses_new_pool_genres(qtbot) -> None:
    service = FakeCandidateService()
    service.chip_options = {"genres": [{"label": "Drama"}], "countries": []}
    _service, _session, filters_view, _list_view = _build_views(qtbot, service=service)

    initial_count = len(filters_view._include_genre_selector._chips)
    service.chip_options = {
        "genres": [{"label": "Drama"}, {"label": "Comedy"}, {"label": "Animation"}],
        "countries": [{"code": "JP", "label": "Japan"}],
    }

    filters_view.reload_filter_options()

    assert initial_count == 1
    assert len(filters_view._include_genre_selector._chips) == 3
    assert len(filters_view._exclude_genre_selector._chips) == 3
    assert filters_view._country_selector._codes_in_order == ["JP"]


def test_country_filter_labels_follow_interface_language(monkeypatch, qtbot) -> None:
    from candidates.models import country_schema
    import desktop.candidates.filters_view as filters_module

    monkeypatch.setattr(filters_module, "get_persisted_interface_language", lambda: "ru")
    monkeypatch.setattr(filters_module, "get_persisted_data_language", lambda: "en")

    service = FakeCandidateService()
    service.chip_options = {
        "genres": [],
        "countries": [
            {"code": "GB", "label": "United Kingdom"},
            {"code": "CA", "label": "Canada"},
            {"code": "RU", "label": "Russia"},
            {"code": "US", "label": "United States"},
        ],
    }

    _service, _session, filters_view, _list_view = _build_views(qtbot, service=service)
    expected_labels = [
        country_schema.build_country_display([code], language="ru")
        for code in ("GB", "CA", "RU", "US")
    ]

    labels = [chip.text() for chip in filters_view._country_selector._ordered_chips()]

    assert labels == expected_labels
    assert "United Kingdom" not in labels

    filters_view._country_selector.set_selected_codes(["GB"])

    assert filters_view._summary_countries_text() == country_schema.build_country_display(["GB"], language="ru")


def test_searchable_candidate_without_kp_imdb_is_visible_in_searchable_mode(qtbot) -> None:
    _service, session, _filters_view, list_view = _build_views(qtbot)

    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})

    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: "Searchable Only" in _listed_titles(list_widget))
    assert "Searchable Only" in _listed_titles(list_widget)


def test_searchable_candidate_without_kp_imdb_is_hidden_in_predict_ready_mode(qtbot) -> None:
    _service, session, _filters_view, list_view = _build_views(qtbot)

    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": True})

    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 1)
    assert _listed_titles(list_widget) == ["Predict Ready"]


def test_selecting_candidate_row_updates_detail_card_and_missing_poster_placeholder(qtbot) -> None:
    _service, session, _filters_view, list_view = _build_views(qtbot)
    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 2)

    row = _listed_titles(list_widget).index("Searchable Only")
    list_widget.setCurrentIndex(list_widget.model().index(row, 0))

    title_label = list_view.widget.findChild(QLabel, "detailTitle")
    poster_label = list_view.widget.findChild(QLabel, "detailPoster")
    assert title_label is not None
    assert poster_label is not None
    qtbot.waitUntil(lambda: "Searchable Only" in title_label.text())
    assert poster_label.text() == "Нет постера"


def test_hide_button_calls_deck_service_and_removes_candidate_row(qtbot) -> None:
    service, session, _filters_view, list_view = _build_views(qtbot)
    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 2)
    list_widget.setCurrentIndex(list_widget.model().index(_listed_titles(list_widget).index("Searchable Only"), 0))

    hide_button = list_view.widget.findChild(QPushButton, "recommendationHiddenButton")
    assert hide_button is not None
    qtbot.waitUntil(lambda: hide_button.isEnabled())
    hide_button.click()

    qtbot.waitUntil(lambda: _listed_count(list_widget) == 1)
    assert [candidate["title"] for candidate in service.hidden_candidates] == ["Searchable Only"]
    assert _listed_titles(list_widget) == ["Predict Ready"]


def test_filter_change_updates_candidate_list(qtbot) -> None:
    _service, session, filters_view, list_view = _build_views(qtbot)
    list_widget = _candidate_list(list_view)
    apply_button = filters_view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    only_complete = filters_view.widget.findChild(QCheckBox, "candidateSearchOnlyComplete")
    assert apply_button is not None
    assert only_complete is not None

    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not session.is_loading)
    assert _listed_titles(list_widget) == ["Predict Ready", "Searchable Only"]

    only_complete.setChecked(True)
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: _listed_count(list_widget) == 1)
    assert _listed_titles(list_widget) == ["Predict Ready"]


def test_media_type_filter_updates_candidate_list(qtbot) -> None:
    service = FakeCandidateService(
        [
            {**_predict_ready_candidate(), "title": "Ready Series", "media_type": "tv"},
            {**_predict_ready_candidate(), "pool_entry_key": "ready-movie|2023|movie", "title": "Ready Movie", "media_type": "movie"},
        ]
    )
    _service, _session, filters_view, list_view = _build_views(qtbot, service)
    list_widget = _candidate_list(list_view)
    apply_button = filters_view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    media_type_combo = filters_view.widget.findChild(QComboBox, "candidateSearchMediaType")

    assert apply_button is not None
    assert media_type_combo is not None
    assert [media_type_combo.itemText(index) for index in range(media_type_combo.count())] == [
        "Всё",
        "Сериал",
        "Фильм",
    ]

    filters_view._form.discovery_media_control.setValue("movie")
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: _listed_titles(list_widget) == ["Ready Movie"])
    assert service.applied_filters[-1]["media_type"] == "movie"


def test_filter_reset_button_stages_defaults_until_apply(qtbot) -> None:
    service, _session, filters_view, list_view = _build_views(qtbot)
    list_widget = _candidate_list(list_view)
    apply_button = filters_view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    reset_button = filters_view.widget.findChild(QPushButton, "candidateSearchResetTopButton")
    only_complete = filters_view.widget.findChild(QCheckBox, "candidateSearchOnlyComplete")
    only_unwatched = filters_view.widget.findChild(QCheckBox, "candidateSearchOnlyUnwatched")
    assert apply_button is not None
    assert reset_button is not None
    assert only_complete is not None
    assert only_unwatched is not None

    only_complete.setChecked(True)
    only_unwatched.setChecked(True)
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 1)

    qtbot.mouseClick(reset_button, Qt.MouseButton.LeftButton)
    assert _listed_count(list_widget) == 1
    assert apply_button.property("pendingChanges") is True

    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 2)

    assert only_complete.isChecked() is False
    assert only_unwatched.isChecked() is True
    assert service.applied_filters[-1] == {**DEFAULT_BROWSE_FILTERS, "animation_mode": "any"}
    assert _listed_titles(list_widget) == ["Predict Ready", "Searchable Only"]


def test_candidate_list_model_roles_and_poster_cache(monkeypatch, qtbot) -> None:
    calls: list[str] = []

    def fake_resolve(candidate: dict) -> str | None:
        calls.append(candidate["title"])
        return f"poster-{candidate['title']}.jpg"

    monkeypatch.setattr("desktop.candidates.list_model.resolve_local_poster_path_for_candidate", fake_resolve)

    model = CandidateListModel([_searchable_candidate()])
    qtbot.addWidget(QListView())
    index = model.index(0, 0)

    assert model.rowCount() == 1
    assert model.data(index, CandidateListRoles.CandidateRole)["title"] == "Searchable Only"
    assert model.data(index, CandidateListRoles.IdentityRole) == "searchable-only|2024"
    assert model.data(index, CandidateListRoles.PosterPathRole) == "poster-Searchable Only.jpg"
    assert model.data(index, CandidateListRoles.PosterPathRole) == "poster-Searchable Only.jpg"
    assert calls == ["Searchable Only"]


def test_session_reuses_cached_overview_for_repeated_filters(qtbot) -> None:
    service, session, _filters_view, _list_view = _build_views(qtbot)

    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": True})

    assert service.overview_calls == 1


def test_session_reload_from_pool_force_refreshes_overview(qtbot) -> None:
    service, session, _filters_view, _list_view = _build_views(qtbot)

    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    session.reload_from_pool(force=True)

    assert service.overview_calls == 2


def test_session_ignores_stale_async_result(qtbot) -> None:
    _service, session, _filters_view, _list_view = _build_views(qtbot)
    session._request_id = 2

    session._on_async_result(
        1,
        {**DEFAULT_BROWSE_FILTERS, "only_complete": False},
        {
            "ok": True,
            "is_empty_pool": False,
            "filtered_count": 1,
            "candidates": [_searchable_candidate()],
            "filtered_candidates": [_searchable_candidate()],
            "hidden_duplicates": 0,
        },
    )

    assert session.has_results is False
    assert session.sorted_total_count() == 0


def test_candidate_search_worker_logs_service_error(monkeypatch, qapp) -> None:
    from desktop.candidates.workers import search_worker as worker_module

    class BrokenService:
        def get_search_overview_view(self):
            raise RuntimeError("service failed")

    logged = []
    completed = []
    monkeypatch.setattr(
        worker_module,
        "log_exception",
        lambda event, error, **fields: logged.append((event, str(error), fields)),
    )
    worker = worker_module.CandidateSearchWorker(
        request_id=7,
        service=BrokenService(),
        filters={},
        sort_mode="final_score",
    )
    worker.completed.connect(lambda request_id, result: completed.append((request_id, result)))

    worker.run()

    assert logged == [
        ("candidates.search.worker.error", "service failed", {"request_id": 7})
    ]
    assert completed[0][0] == 7
    assert completed[0][1]["ok"] is False


def test_fts_disabled_falls_back_to_substring_filter(qtbot) -> None:
    service = FakeCandidateService()
    service.set_fts_enabled(False)
    _service, session, _filters_view, list_view = _build_views(qtbot, service=service)
    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 2)

    search_input = list_view.widget.findChild(QLineEdit, "candidateListSearch")
    assert search_input is not None
    search_input.setText("Searchable")
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 1)

    assert service.applied_text_queries == []
    assert _listed_titles(list_widget) == ["Searchable Only"]


def test_recommendation_search_remains_local_when_fts_is_enabled(qtbot) -> None:
    service = FakeCandidateService()
    service.set_fts_enabled(True)
    _service, session, _filters_view, list_view = _build_views(qtbot, service=service)
    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 2)

    search_input = list_view.widget.findChild(QLineEdit, "candidateListSearch")
    assert search_input is not None
    search_input.setText("Searchable")
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 1)

    assert service.applied_text_queries == []
    assert _listed_titles(list_widget) == ["Searchable Only"]


def test_fts_refresh_selects_first_candidate_and_updates_pool_count(qtbot) -> None:
    service = FakeCandidateService()
    service.set_fts_enabled(True)
    _service, session, _filters_view, list_view = _build_views(qtbot, service=service)

    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 2)

    detail_scroll = list_view.widget.findChild(QScrollArea, "candidateSearchDetailScroll")
    counter = list_view.widget.findChild(QLabel, "candidateListCounter")

    assert list_widget.currentIndex().row() == 0
    assert detail_scroll is not None and detail_scroll.isHidden() is False
    assert counter is not None and "2" in counter.text()
    assert "pool: 0" not in counter.text()


def test_detail_card_shows_search_reasons_when_fts_context_present(qtbot) -> None:
    from desktop.candidates.presenters import build_candidate_readonly_detail_entry

    candidate = {
        **_searchable_candidate(),
        "text_relevance_score": 0.82,
        "matched_fields": ["title"],
    }
    _entry_key, _movie, card = build_candidate_readonly_detail_entry(
        candidate,
        filters=DEFAULT_BROWSE_FILTERS,
        search_context={"text_query": "searchable"},
    )
    assert card.get("search_reasons")
    assert any("BM25" in line or "Совпадение" in line for line in card["search_reasons"])

    service = FakeCandidateService([candidate])
    service.set_fts_enabled(True)
    _service, session, _filters_view, list_view = _build_views(qtbot, service=service)
    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 1)

    session._last_search_context = {
        "text_query": "Searchable",
        "filters": dict(DEFAULT_BROWSE_FILTERS),
        "sort_mode": session.sort_mode,
    }
    list_view._detail_entries.clear()
    list_view._on_result_selected(list_widget.model().index(0, 0))

    title_meta = list_view.widget.findChild(QLabel, "detailTitleMeta")
    assert title_meta is not None
    qtbot.waitUntil(lambda: "BM25" in title_meta.text() or "Совпадение" in title_meta.text())
