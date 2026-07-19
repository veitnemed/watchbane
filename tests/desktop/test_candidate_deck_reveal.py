from __future__ import annotations

from copy import deepcopy
from threading import Event

from PyQt6.QtWidgets import QStackedWidget

from desktop.candidates.empty_state import RecommendationEmptyState
from desktop.candidates import list_view as list_view_module
from desktop.candidates.list_view import CandidateListView
from desktop.i18n import tr
from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS


class _Signal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args) -> None:
        for callback in tuple(self._callbacks):
            callback(*args)


class FakePosterPrefetchController:
    def __init__(self, **_kwargs) -> None:
        self.poster_ready = _Signal()
        self.busy_changed = _Signal()
        self.network_cycle_finished = _Signal()
        self.batch_started = _Signal()
        self.candidate_settled = _Signal()
        self.batch_progress = _Signal()
        self.batch_finished = _Signal()
        self.background_calls: list[list[dict]] = []
        self.batch_calls: list[list[dict]] = []
        self.cancel_count = 0
        self._next_batch_id = 0

    def allow_failed_retries(self, **_kwargs) -> None:
        return None

    def enqueue_candidates(self, candidates: list[dict], **_kwargs) -> None:
        self.background_calls.append(deepcopy(candidates))

    def start_batch(self, candidates: list[dict], **_kwargs) -> int:
        self._next_batch_id += 1
        batch_id = self._next_batch_id
        snapshot = deepcopy(candidates)
        self.batch_calls.append(snapshot)
        self.batch_started.emit(batch_id, len(snapshot))
        for settled, candidate in enumerate(snapshot, start=1):
            identity = str(candidate["pool_entry_key"])
            self.candidate_settled.emit(batch_id, identity, "poster.png", False, True)
            self.batch_progress.emit(batch_id, settled, 0, settled, len(snapshot), settled)
        self.batch_finished.emit(batch_id, len(snapshot), 0, len(snapshot), len(snapshot))
        return batch_id

    def enqueue(self, *_args, **_kwargs) -> None:
        return None

    def cancel_pending(self) -> None:
        self.cancel_count += 1


class FakeCandidateService:
    def is_fts_search_enabled(self) -> bool:
        return False


class FakeDeckService:
    def __init__(self, deck: dict) -> None:
        self.deck = deepcopy(deck)
        self.calls = 0

    def refresh_deck(self, _preferences: dict, _now, **_kwargs) -> dict:
        self.calls += 1
        return deepcopy(self.deck)


class BlockingDeckService(FakeDeckService):
    def __init__(self, deck: dict) -> None:
        super().__init__(deck)
        self.first_started = Event()
        self.release_first = Event()

    def refresh_deck(self, _preferences: dict, _now, **kwargs) -> dict:
        self.calls += 1
        if self.calls == 1:
            self.first_started.set()
            self.release_first.wait(2.0)
        result = deepcopy(self.deck)
        result["variation_seed"] = int(kwargs.get("variation_seed") or 0)
        result["deck_id"] = f"deck-{self.calls}"
        return result


def _candidate(index: int) -> dict:
    return {
        "pool_entry_key": f"candidate-{index}|2024|movie",
        "title": f"Candidate {index:02d}",
        "year": 2024,
        "media_type": "movie",
        "tmdb_score": 7.5,
        "tmdb_votes": 500,
        "final_score": 75.0 - index / 100,
        "overview": "Candidate overview.",
        "is_searchable": True,
        "is_complete": True,
    }


def _deck() -> dict:
    active = [_candidate(index) for index in range(10)]
    return {
        "deck_id": "progressive-deck",
        "preferences": deepcopy(DEFAULT_BROWSE_FILTERS),
        "recommendation_vector": {},
        "variation_seed": 0,
        "active": active,
        "reserve": [_candidate(100 + index) for index in range(70)],
        "active_limit": 10,
        "reserve_size": 70,
        "refill_needed": False,
        "underfilled_reason": None,
        "excluded": {"pool_total": 95},
    }


def _build_view(qtbot, monkeypatch, *, deck_service=None) -> CandidateListView:
    monkeypatch.setattr(
        list_view_module,
        "CandidatePosterPrefetchController",
        FakePosterPrefetchController,
    )
    monkeypatch.setattr(
        list_view_module,
        "candidate_needs_tmdb_detail_enrichment",
        lambda _candidate, _language: False,
    )
    service = FakeCandidateService()
    session = CandidateSearchSession(service=service)
    session.filters = deepcopy(DEFAULT_BROWSE_FILTERS)
    view = CandidateListView(
        session,
        service=service,
        deck_service=deck_service or FakeDeckService(_deck()),
    )
    view.widget._test_controller = view
    qtbot.addWidget(view.widget)
    view.widget.show()
    return view


def _stack(view: CandidateListView) -> QStackedWidget:
    stack = view.widget.findChild(QStackedWidget, "recommendationsDeckStack")
    assert stack is not None
    return stack


def test_deck_loading_page_uses_one_right_side_preparing_overlay(qtbot, monkeypatch) -> None:
    view = _build_view(qtbot, monkeypatch)

    view._begin_deck_preparation()

    overlays = view._deck_loading_page.findChildren(RecommendationEmptyState)
    assert overlays == [view._deck_loading_state]
    assert view._deck_loading_state.objectName() == "recommendationsDeckLoadingOverlay"
    assert view._deck_loading_state.title_label.text() == tr("recommendations.preparing.title")
    assert view._deck_loading_state.subtitle_label.text() == tr("recommendations.preparing.detail")
    assert _stack(view).currentWidget() is view._deck_loading_page


def test_deck_content_is_revealed_after_the_poster_waiting_screen(qtbot, monkeypatch) -> None:
    view = _build_view(qtbot, monkeypatch)

    view.on_tab_activated()
    qtbot.waitUntil(lambda: view._deck_worker is None and view._deck is not None)

    controller = view._poster_prefetch
    assert _stack(view).currentWidget() is view._deck_loading_page
    qtbot.waitUntil(lambda: _stack(view).currentWidget() is view._deck_content_page)
    assert _stack(view).currentWidget() is view._deck_content_page
    assert len(view._all_candidates) == 10
    assert len(controller.batch_calls) == 1
    assert len(controller.batch_calls[0]) == 10


def test_replaced_deck_cancels_stale_poster_requests(qtbot, monkeypatch) -> None:
    service = FakeDeckService(_deck())
    view = _build_view(qtbot, monkeypatch, deck_service=service)
    view.on_tab_activated()
    qtbot.waitUntil(lambda: view._deck_worker is None and view._deck is not None)
    initial_cancel_count = view._poster_prefetch.cancel_count

    service.deck["deck_id"] = "replacement"
    view._load_recommendation_deck(force_new=True)
    qtbot.waitUntil(lambda: view._deck_worker is None and view._deck["deck_id"] == "replacement")

    assert view._poster_prefetch.cancel_count == initial_cancel_count + 1
    assert _stack(view).currentWidget() is view._deck_loading_page
    qtbot.waitUntil(lambda: _stack(view).currentWidget() is view._deck_content_page)
    assert _stack(view).currentWidget() is view._deck_content_page


def test_deck_requests_coalesce_to_latest_generation(qtbot, monkeypatch) -> None:
    service = BlockingDeckService(_deck())
    view = _build_view(qtbot, monkeypatch, deck_service=service)
    view._recommendations_active = True

    view._load_recommendation_deck(force_new=False)
    assert service.first_started.wait(1.0)
    view._session.variation_seed = 2
    view._load_recommendation_deck(force_new=True)
    service.release_first.set()

    qtbot.waitUntil(lambda: view._deck_worker is None and service.calls == 2)

    assert view._deck["deck_id"] == "deck-2"
    assert view._deck["variation_seed"] == 2
