from __future__ import annotations

from copy import deepcopy
from time import perf_counter

from PyQt6.QtWidgets import QStackedWidget

from desktop.candidates import list_view as list_view_module
from desktop.candidates.list_view import CandidateListView
from desktop.candidates.presenters import candidate_detail_identity
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
        self.batch_id = 0
        self.start_calls: list[list[dict]] = []
        self.background_calls: list[list[dict]] = []

    def allow_failed_retries(self, **_kwargs) -> None:
        return None

    def start_batch(self, candidates: list[dict], **_kwargs) -> int:
        self.batch_id += 1
        self.start_calls.append(deepcopy(candidates))
        self.batch_started.emit(self.batch_id, len(candidates))
        self.batch_progress.emit(self.batch_id, 0, 0, 0, len(candidates), 0)
        return self.batch_id

    def enqueue_candidates(self, candidates: list[dict], **_kwargs) -> None:
        self.background_calls.append(deepcopy(candidates))

    def enqueue(self, *_args, **_kwargs) -> None:
        return None


class FakeCandidateService:
    def is_fts_search_enabled(self) -> bool:
        return False


class FakeDeckService:
    def __init__(self, deck: dict) -> None:
        self.deck = deepcopy(deck)

    def refresh_deck(self, _preferences: dict, _now, *, force_new: bool = False) -> dict:
        del force_new
        return deepcopy(self.deck)


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
    active = [_candidate(index) for index in range(25)]
    return {
        "deck_id": "reveal-deck",
        "preferences": deepcopy(DEFAULT_BROWSE_FILTERS),
        "active": active,
        "reserve": [_candidate(100 + index) for index in range(70)],
        "active_limit": 25,
        "reserve_size": 70,
        "refill_needed": False,
        "underfilled_reason": None,
        "excluded": {"pool_total": 95},
    }


def _build_view(qtbot, monkeypatch) -> CandidateListView:
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
        deck_service=FakeDeckService(_deck()),
    )
    view.widget._test_controller = view
    qtbot.addWidget(view.widget)
    view.widget.show()
    view.on_tab_activated()
    qtbot.waitUntil(lambda: view._deck_prepare_batch_id is not None)
    return view


def _stack(view: CandidateListView) -> QStackedWidget:
    stack = view.widget.findChild(QStackedWidget, "recommendationsDeckStack")
    assert stack is not None
    return stack


def _settle(
    view: CandidateListView,
    indices: list[int],
    *,
    settled_total: int,
) -> None:
    controller = view._poster_prefetch
    batch_id = view._deck_prepare_batch_id
    assert batch_id is not None
    for index in indices:
        identity = candidate_detail_identity(view._all_candidates[index])
        controller.candidate_settled.emit(batch_id, identity, "", False, False)
    controller.batch_progress.emit(batch_id, 0, 0, settled_total, 25, 0)


def test_reveal_requires_first_eight_and_twenty_settled(qtbot, monkeypatch) -> None:
    view = _build_view(qtbot, monkeypatch)
    view._deck_loader_shown_at = perf_counter() - 1.0

    _settle(view, list(range(7)) + list(range(8, 21)), settled_total=20)
    assert _stack(view).currentWidget() is view._deck_loading_page


def test_reveal_opens_at_exactly_twenty_when_first_eight_are_settled(qtbot, monkeypatch) -> None:
    view = _build_view(qtbot, monkeypatch)
    view._deck_loader_shown_at = perf_counter() - 1.0

    _settle(view, list(range(20)), settled_total=20)
    assert _stack(view).currentWidget() is view._deck_content_page


def test_reveal_deadline_opens_deck_with_pending_posters(qtbot, monkeypatch) -> None:
    view = _build_view(qtbot, monkeypatch)
    view._deck_loader_shown_at = perf_counter() - 1.0
    _settle(view, [0, 1, 2], settled_total=3)

    assert view._deck_deadline_timer.isActive()
    assert view._deck_deadline_timer.interval() == list_view_module.POSTER_REVEAL_DEADLINE_MS
    view._on_deck_deadline()

    assert _stack(view).currentWidget() is view._deck_content_page


def test_fast_batch_waits_for_minimum_loader_interval(qtbot, monkeypatch) -> None:
    view = _build_view(qtbot, monkeypatch)
    view._deck_loader_shown_at = perf_counter()
    _settle(view, list(range(25)), settled_total=25)

    assert _stack(view).currentWidget() is view._deck_loading_page
    assert view._deck_minimum_timer.isActive()

    view._deck_loader_shown_at = perf_counter() - 1.0
    view._on_deck_minimum_elapsed()
    assert _stack(view).currentWidget() is view._deck_content_page


def test_stale_batch_progress_is_ignored_by_reveal_gate(qtbot, monkeypatch) -> None:
    view = _build_view(qtbot, monkeypatch)
    controller = view._poster_prefetch
    old_batch_id = view._deck_prepare_batch_id
    assert old_batch_id is not None
    view._deck_loader_shown_at = perf_counter() - 1.0

    controller.batch_started.emit(old_batch_id + 1, 25)
    controller.batch_progress.emit(old_batch_id, 25, 0, 25, 25, 25)

    assert view._deck_prepare_batch_id == old_batch_id + 1
    assert _stack(view).currentWidget() is view._deck_loading_page


def test_same_deck_refill_stays_on_content_page(qtbot, monkeypatch) -> None:
    view = _build_view(qtbot, monkeypatch)
    view._deck_loader_shown_at = perf_counter() - 1.0
    view._on_deck_deadline()
    controller = view._poster_prefetch
    assert len(controller.start_calls) == 1

    updated = deepcopy(view._deck)
    updated["active"] = list(updated["active"])[1:] + [_candidate(200)]
    view._present_recommendation_deck(updated, prepare_posters=False)

    assert _stack(view).currentWidget() is view._deck_content_page
    assert len(controller.start_calls) == 1
    assert len(controller.background_calls) == 1


def test_force_new_deck_returns_to_loading_page(qtbot, monkeypatch) -> None:
    view = _build_view(qtbot, monkeypatch)
    view._deck_loader_shown_at = perf_counter() - 1.0
    view._on_deck_deadline()
    controller = view._poster_prefetch
    assert _stack(view).currentWidget() is view._deck_content_page

    view._on_new_deck_clicked()

    assert _stack(view).currentWidget() is view._deck_loading_page
    assert len(controller.start_calls) == 2
    assert view._deck_prepare_batch_id == 2
