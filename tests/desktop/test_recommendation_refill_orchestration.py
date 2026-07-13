from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QStackedWidget

from candidates import service as candidate_service
from candidates.preferences import SimpleRecommendationPreferences
from desktop.candidates import filters_view as filters_view_module
from desktop.candidates import list_view as list_view_module
from desktop.candidates.filters_view import CandidateFiltersView
from desktop.candidates.list_view import CandidateListView
from desktop.candidates.presenters import candidate_detail_identity
from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS


def _candidate(
    index: int,
    *,
    country: str,
    genres: list[str],
    media_type: str = "tv",
) -> dict:
    return {
        "pool_entry_key": f"candidate-{index}|2024|{media_type}",
        "title": f"Candidate {index:03d}",
        "year": 2024,
        "media_type": media_type,
        "tmdb_id": 10_000 + index,
        "country": country,
        "country_codes": [country],
        "genres": list(genres),
        "genres_tmdb": list(genres),
        "tmdb_score": 7.5,
        "tmdb_votes": 500,
        "final_score": 75.0,
        "description": "A complete candidate overview.",
        "is_searchable": True,
        "is_complete": True,
    }


class RefillOrchestrationService:
    SEARCH_SORT_MODES = ("final_score", "relevance")
    SEARCH_SORT_MODE_LABELS = {
        "final_score": "Final score",
        "relevance": "Relevance",
    }

    def __init__(self, candidates: list[dict]) -> None:
        self.candidates = deepcopy(candidates)

    def get_search_overview_view(self) -> dict:
        total = len(self.candidates)
        return {
            "is_empty": total == 0,
            "summary": f"{total} candidates",
            "stats": {
                "unique_total": total,
                "storage_total": total,
                "active_total": total,
                "eligible_total": 2,
                "recommendation_eligible_total": 2,
            },
            "candidates": deepcopy(self.candidates),
        }

    @staticmethod
    def _country_codes(candidate: dict) -> set[str]:
        values = candidate.get("country_codes") or candidate.get("country") or []
        if isinstance(values, str):
            values = [values]
        return {str(value).strip().upper() for value in values if str(value).strip()}

    @staticmethod
    def _genre_keys(candidate: dict) -> set[str]:
        values = candidate.get("genres") or candidate.get("genres_tmdb") or []
        return {str(value).strip().casefold() for value in values if str(value).strip()}

    def search_candidate_pool(self, candidates: list[dict], filters: dict) -> dict:
        requested_countries = filters.get("country") or filters.get("countries") or []
        if isinstance(requested_countries, str):
            requested_countries = [requested_countries]
        country_codes = {
            str(value).strip().upper()
            for value in requested_countries
            if str(value).strip()
        }
        media_type = filters.get("media_type")
        include_genres = {
            str(value).strip().casefold()
            for value in filters.get("include_genres") or []
            if str(value).strip()
        }
        result = []
        for candidate in candidates:
            if media_type not in (None, "", "both", candidate.get("media_type")):
                continue
            if country_codes and not (country_codes & self._country_codes(candidate)):
                continue
            if include_genres and not (include_genres & self._genre_keys(candidate)):
                continue
            result.append(candidate)
        return {"candidates": result, "filtered_count": len(result)}

    def get_search_filter_view(self, candidates: list[dict], filters: dict) -> dict:
        return self.search_candidate_pool(candidates, filters)

    def sort_search_candidates(self, candidates: list[dict], sort_mode: str) -> dict:
        return {
            "candidates": list(candidates),
            "sort_mode": sort_mode,
            "hidden_duplicates": 0,
        }

    def get_search_filter_defaults_view(self) -> dict:
        return {"defaults": dict(DEFAULT_BROWSE_FILTERS)}

    def get_search_filter_chip_options_view(self) -> dict:
        return {
            "genres": [
                {"key": "crime", "label": "Crime"},
                {"key": "mystery", "label": "Mystery"},
                {"key": "thriller", "label": "Thriller"},
                {"key": "comedy", "label": "Comedy"},
            ],
            "countries": [
                {"code": "RU", "label": "Russia"},
                {"code": "US", "label": "United States"},
            ],
        }


class _Signal:
    def __init__(self) -> None:
        self._callbacks: list = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback) -> None:
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def emit(self, *args) -> None:
        for callback in list(self._callbacks):
            callback(*args)


def _install_blocking_replenish_worker(monkeypatch):
    workers: list = []

    class BlockingReplenishWorker:
        def __init__(self, *args, **kwargs) -> None:
            intent = kwargs.get("intent")
            if intent is None:
                intent = next((value for value in args if isinstance(value, dict)), {})
            self.intent = deepcopy(dict(intent or {}))
            self.progress = _Signal()
            self.finished_with_result = _Signal()
            self.failed = _Signal()
            self.finished = _Signal()
            self.cancelled = False
            self.running = False
            workers.append(self)

        def start(self) -> None:
            self.running = True

        def cancel(self) -> None:
            self.cancelled = True

        def requestInterruption(self) -> None:  # pragma: no cover - compatibility seam
            self.cancel()

        def isRunning(self) -> bool:
            return self.running

        def emit_result(self, result: dict) -> None:
            self.finished_with_result.emit(deepcopy(result))

        def finish_thread(self) -> None:
            self.running = False
            self.finished.emit()

        def deleteLater(self) -> None:
            return None

    monkeypatch.setattr(filters_view_module, "FilterReplenishWorker", BlockingReplenishWorker)
    return workers


def _build_filters_view(qtbot, monkeypatch, candidates: list[dict]):
    monkeypatch.setattr(
        filters_view_module,
        "load_simple_recommendation_preferences",
        lambda: SimpleRecommendationPreferences(),
    )
    monkeypatch.setattr(
        filters_view_module,
        "save_simple_recommendation_preferences",
        lambda _preferences: None,
    )
    service = RefillOrchestrationService(candidates)
    session = CandidateSearchSession(service=service)
    view = CandidateFiltersView(session, service=service)
    qtbot.addWidget(view.widget)
    view.widget.show()
    return service, session, view


def _set_combo_data(combo, value: str) -> None:
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def _dark_ru_preferences(*, country: str = "RU", vibe: str = "dark") -> dict:
    return {
        **DEFAULT_BROWSE_FILTERS,
        "country": [country],
        "countries": [country],
        "media_type": "tv",
        "vibe": vibe,
        "genre_groups": ["thriller", "crime"] if vibe == "dark" else ["comedy"],
        "_recommendation_mood": vibe,
    }


def _intent_countries(intent: dict) -> set[str]:
    values = intent.get("countries") or intent.get("country") or []
    if isinstance(values, str):
        values = [values]
    return {str(value).strip().upper() for value in values if str(value).strip()}


def test_simple_apply_refills_when_total_pool_is_large_but_matching_slice_is_small(
    qtbot,
    monkeypatch,
) -> None:
    candidates = [
        _candidate(index, country="US", genres=["Comedy"])
        for index in range(38)
    ] + [
        _candidate(100, country="RU", genres=["Crime", "Thriller"]),
        _candidate(101, country="RU", genres=["Mystery", "Drama"]),
    ]
    workers = _install_blocking_replenish_worker(monkeypatch)
    _service, session, view = _build_filters_view(qtbot, monkeypatch, candidates)
    direction_values = view._form.direction_control.property("directionValues")
    view._form.direction_control.setValue(direction_values.index("russian_mainstream"))
    view._form.discovery_media_control.setValue("tv")
    view._form.vector_mood_control.setValue("dark")
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    assert apply_button is not None

    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: session.is_loading is False and session.filters is not None)
    qtbot.waitUntil(lambda: len(workers) == 1)

    assert len(candidates) > 30
    assert session.filtered_count == 1
    assert _intent_countries(workers[0].intent) == {"RU"}
    assert workers[0].intent.get("vibe") == "mixed"


def test_repeated_identical_refill_request_starts_only_one_worker(qtbot, monkeypatch) -> None:
    workers = _install_blocking_replenish_worker(monkeypatch)
    _service, _session, view = _build_filters_view(
        qtbot,
        monkeypatch,
        [_candidate(1, country="RU", genres=["Crime"])],
    )
    preferences = _dark_ru_preferences()

    first_started = view.request_recommendation_refill(deepcopy(preferences))
    second_started = view.request_recommendation_refill(deepcopy(preferences))

    assert first_started is True
    assert second_started is False
    assert len(workers) == 1
    assert workers[0].running is True


def test_shutdown_clears_queued_refill_and_does_not_restart_worker(qtbot, monkeypatch) -> None:
    workers = _install_blocking_replenish_worker(monkeypatch)
    _service, _session, view = _build_filters_view(
        qtbot,
        monkeypatch,
        [_candidate(1, country="RU", genres=["Crime"])],
    )
    first_intent = {"countries": ["RU"], "target_add_count": 30}
    queued_intent = {"countries": ["US"], "target_add_count": 30}
    assert view._start_filter_replenish(first_intent) is True
    view._pending_replenish_intent = queued_intent
    view._pending_replenish_generation = view._replenish_generation

    view.prepare_for_shutdown()
    workers[0].finish_thread()

    assert workers[0].cancelled is True
    assert view._pending_replenish_intent is None
    assert view._pending_replenish_generation is None
    assert len(workers) == 1


def test_changed_refill_preferences_cancel_active_and_ignore_its_stale_result(
    qtbot,
    monkeypatch,
) -> None:
    workers = _install_blocking_replenish_worker(monkeypatch)
    _service, session, view = _build_filters_view(
        qtbot,
        monkeypatch,
        [_candidate(1, country="RU", genres=["Crime"])],
    )
    reload_calls: list[bool] = []

    def reload_from_pool(*, force: bool = False) -> dict:
        reload_calls.append(bool(force))
        return {"ok": True, "visible_count": session.filtered_count}

    monkeypatch.setattr(session, "reload_from_pool", reload_from_pool)
    first_preferences = _dark_ru_preferences(country="RU", vibe="dark")
    second_preferences = _dark_ru_preferences(country="US", vibe="light")

    assert view.request_recommendation_refill(first_preferences) is True
    first_worker = workers[0]
    view.request_recommendation_refill(second_preferences)

    assert first_worker.cancelled is True
    first_worker.emit_result(
        {
            "ok": True,
            "requested_count": 30,
            "created_count": 30,
            "saved_count": 30,
        }
    )
    assert reload_calls == []
    assert view._last_replenish_result is None

    first_worker.finish_thread()
    qtbot.waitUntil(lambda: any(_intent_countries(worker.intent) == {"US"} for worker in workers))
    assert len([worker for worker in workers if _intent_countries(worker.intent) == {"US"}]) == 1


class FakeDeckService:
    def __init__(self, initial_deck: dict, *, action_deck: dict | None = None) -> None:
        self.initial_deck = deepcopy(initial_deck)
        self.action_deck = deepcopy(action_deck) if action_deck is not None else None
        self.action_calls: list[tuple[str, str]] = []

    def refresh_deck(self, _preferences: dict, _now, *, force_new: bool = False) -> dict:
        del force_new
        return deepcopy(self.initial_deck)

    def apply_action_and_refill(self, deck_id: str, candidate: dict, action: str) -> dict:
        self.action_calls.append((action, candidate_detail_identity(candidate)))
        assert deck_id == self.initial_deck["deck_id"]
        assert self.action_deck is not None
        return deepcopy(self.action_deck)


class FakePosterPrefetchController:
    def __init__(self, **_kwargs) -> None:
        self.poster_ready = _Signal()
        self.busy_changed = _Signal()
        self.network_cycle_finished = _Signal()
        self.batch_started = _Signal()
        self.candidate_settled = _Signal()
        self.batch_progress = _Signal()
        self.batch_finished = _Signal()
        self._batch_id = 0

    def allow_failed_retries(self, **_kwargs) -> None:
        return None

    def enqueue_candidates(self, _candidates: list[dict], **_kwargs) -> None:
        return None

    def start_batch(self, candidates: list[dict], **_kwargs) -> int:
        self._batch_id += 1
        batch_id = self._batch_id
        total = len(candidates)
        self.batch_started.emit(batch_id, total)
        self.batch_progress.emit(batch_id, 0, 0, 0, total, 0)
        for settled, candidate in enumerate(candidates, start=1):
            identity = candidate_detail_identity(candidate)
            self.candidate_settled.emit(batch_id, identity, "", False, False)
            self.batch_progress.emit(batch_id, 0, 0, settled, total, 0)
        self.batch_finished.emit(batch_id, 0, 0, total, 0)
        return batch_id

    def enqueue(self, *_args, **_kwargs) -> None:
        return None


def _deck_payload(
    candidate: dict,
    preferences: dict,
    *,
    refill_needed: bool,
    active: list[dict] | None = None,
) -> dict:
    return {
        "deck_id": "refill-test-deck",
        "preferences": deepcopy(preferences),
        "active": deepcopy([candidate] if active is None else active),
        "reserve": [],
        "active_limit": 25,
        "reserve_size": 70,
        "unknown_rating_limit": 6,
        "refill_needed": refill_needed,
        "underfilled_reason": "active_underfilled" if refill_needed else None,
        "eligible_count": 1,
        "excluded": {"pool_total": 40},
    }


def _build_list_view(
    qtbot,
    monkeypatch,
    *,
    candidate: dict,
    preferences: dict,
    deck_service: FakeDeckService,
    refill_calls: list[dict],
) -> CandidateListView:
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
    service = RefillOrchestrationService([candidate])
    session = CandidateSearchSession(service=service)
    session.filters = deepcopy(preferences)

    def on_refill_needed(payload: dict) -> bool:
        refill_calls.append(deepcopy(dict(payload or {})))
        return True

    view = CandidateListView(
        session,
        service=service,
        deck_service=deck_service,
        on_refill_needed=on_refill_needed,
    )
    view.widget._test_controller = view
    qtbot.addWidget(view.widget)
    view.widget.show()
    view.on_tab_activated()
    qtbot.waitUntil(lambda: view._deck is not None)
    qtbot.waitUntil(
        lambda: view.widget.findChild(QStackedWidget, "recommendationsDeckStack").currentWidget()
        is view._deck_content_page
    )
    return view


def test_candidate_list_requests_refill_for_initial_underfilled_deck() -> None:
    candidate = _candidate(1, country="RU", genres=["Crime"])
    preferences = _dark_ru_preferences()
    refill_calls: list[dict] = []
    deck = _deck_payload(candidate, preferences, refill_needed=True)
    deck["underfilled_reason"] = "reserve_underfilled"
    service = RefillOrchestrationService([candidate])
    session = CandidateSearchSession(service=service)
    session.filters = deepcopy(preferences)
    view = object.__new__(CandidateListView)
    view._session = session
    view._deck = deck
    view._refill_requested_deck_ids = set()
    view._refill_last_attempt = None
    view._on_refill_needed = lambda payload: refill_calls.append(deepcopy(payload)) or True

    view._maybe_request_recommendation_refill()

    assert len(refill_calls) == 1
    assert _intent_countries(refill_calls[0]) == {"RU"}

    view._maybe_request_recommendation_refill()
    assert len(refill_calls) == 1
    assert view._refill_requested_deck_ids == {"refill-test-deck"}


def test_candidate_list_first_activation_requests_underfilled_refill(qtbot, monkeypatch) -> None:
    candidate = _candidate(1, country="RU", genres=["Crime"])
    preferences = _dark_ru_preferences()
    refill_calls: list[dict] = []
    initial = _deck_payload(candidate, preferences, refill_needed=True)
    initial["underfilled_reason"] = "reserve_underfilled"
    view = _build_list_view(
        qtbot,
        monkeypatch,
        candidate=candidate,
        preferences=preferences,
        deck_service=FakeDeckService(initial),
        refill_calls=refill_calls,
    )

    assert view._initial_deck_loaded is True
    assert len(refill_calls) == 1
    assert _intent_countries(refill_calls[0]) == {"RU"}

    view.on_replenish_state_changed("loading")
    assert view._deck_reserve_indicator._mode == "replenishing"
    view.on_replenish_state_changed("error")
    assert view._deck_reserve_indicator._mode == "offline"
    assert view._deck_refill_button.isVisible()

    calls_before_retry = len(refill_calls)
    view._deck_refill_button.click()
    view._deck_refill_button.click()
    assert len(refill_calls) == calls_before_retry + 1


def test_candidate_list_requests_refill_after_action_exhausts_reserve(qtbot, monkeypatch) -> None:
    candidate = _candidate(1, country="RU", genres=["Crime"])
    preferences = _dark_ru_preferences()
    refill_calls: list[dict] = []
    initial = _deck_payload(candidate, preferences, refill_needed=False)
    after_action = {
        **_deck_payload(candidate, preferences, refill_needed=True, active=[]),
        "last_action": {
            "action": "hidden",
            "transition": {"ok": True, "state": "hidden"},
        },
    }
    deck_service = FakeDeckService(initial, action_deck=after_action)
    view = _build_list_view(
        qtbot,
        monkeypatch,
        candidate=candidate,
        preferences=preferences,
        deck_service=deck_service,
        refill_calls=refill_calls,
    )
    assert refill_calls == []
    view._selected_candidate = candidate
    view._selected_identity = candidate_detail_identity(candidate)

    view._apply_recommendation_action("hidden")

    assert deck_service.action_calls == [("hidden", candidate_detail_identity(candidate))]
    assert len(refill_calls) == 1
    assert _intent_countries(refill_calls[0]) == {"RU"}


def test_filter_replenish_rechecks_cancellation_before_import(monkeypatch) -> None:
    from candidates import onboarding_service
    cancellation = {"requested": False}
    imported: list[list[dict]] = []

    monkeypatch.setattr(onboarding_service, "load_candidate_pool", lambda: {})

    def fake_replenish(_intent, **_kwargs) -> dict:
        cancellation["requested"] = True
        return {
            "ok": True,
            "cancelled": False,
            "created_count": 1,
            "saved_count": 0,
            "candidates": [_candidate(1, country="RU", genres=["Crime"])],
            "compatibility": {},
            "plan": {},
        }

    def fake_import(candidates: list[dict], **_kwargs) -> dict:
        imported.append(deepcopy(candidates))
        return {"added": len(candidates)}

    monkeypatch.setattr(onboarding_service, "replenish_candidates_for_filters", fake_replenish)
    monkeypatch.setattr(
        onboarding_service.tmdb_import,
        "import_tmdb_candidates_to_common_pool",
        fake_import,
    )

    result = candidate_service.replenish_candidate_pool_for_filters(
        _dark_ru_preferences(),
        tmdb_client=object(),
        cancel_checker=lambda: cancellation["requested"],
        dry_run=False,
    )

    assert result.get("cancelled") is True
    assert imported == []
