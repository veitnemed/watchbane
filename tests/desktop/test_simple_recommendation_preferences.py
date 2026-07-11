from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QPushButton, QToolButton, QWidget

from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS


def _candidate(index: int) -> dict:
    return {
        "pool_entry_key": f"candidate-{index}|2024|movie",
        "title": f"Candidate {index}",
        "year": 2024,
        "media_type": "movie",
        "is_searchable": True,
        "is_complete": True,
    }


class SimplePreferenceService:
    SEARCH_SORT_MODES = ("final_score",)

    def __init__(self, count: int = 1, *, replenish_ok: bool = True) -> None:
        self.candidates = [_candidate(index) for index in range(count)]
        self.replenish_ok = replenish_ok
        self.replenish_calls: list[dict] = []

    def get_search_overview_view(self) -> dict:
        return {
            "is_empty": not self.candidates,
            "stats": {"unique_total": len(self.candidates), "storage_total": len(self.candidates)},
            "candidates": deepcopy(self.candidates),
        }

    def search_candidate_pool(self, candidates: list[dict], filters: dict) -> dict:
        media_type = filters.get("media_type")
        result = [item for item in candidates if media_type in (None, item.get("media_type"))]
        return {"candidates": result, "filtered_count": len(result)}

    def sort_search_candidates(self, candidates: list[dict], sort_mode: str) -> dict:
        return {"candidates": list(candidates), "sort_mode": sort_mode, "hidden_duplicates": 0}

    def get_search_filter_defaults_view(self) -> dict:
        return {"defaults": dict(DEFAULT_BROWSE_FILTERS)}

    def get_search_filter_chip_options_view(self) -> dict:
        return {"genres": [], "countries": []}

    def replenish_candidate_pool_for_filters(self, intent: dict, **_kwargs) -> dict:
        self.replenish_calls.append(dict(intent))
        if not self.replenish_ok:
            return {"ok": False, "error": "offline", "requested_count": 30, "saved_count": 0}
        return {"ok": True, "requested_count": 30, "saved_count": 0, "created_count": 0}


def _build_view(qtbot, service: SimplePreferenceService):
    from desktop.candidates.filters_view import CandidateFiltersView

    session = CandidateSearchSession(service=service)
    view = CandidateFiltersView(session, service=service)
    qtbot.addWidget(view.widget)
    view.widget.show()
    return session, view


def _set_combo(view, object_name: str, value: str) -> None:
    combo = view.widget.findChild(QComboBox, object_name)
    assert combo is not None
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def test_simple_preferences_map_to_internal_filters_and_pool_plan() -> None:
    from candidates.preferences import SimpleRecommendationPreferences

    preferences = SimpleRecommendationPreferences(
        media="tv",
        collection="new",
        origin="asia",
        mood="dynamic",
    )

    filters = preferences.to_candidate_filters(DEFAULT_BROWSE_FILTERS)
    intent = preferences.to_replenish_intent(data_language="en")

    assert filters["media_type"] == "tv"
    assert filters["country"] == ["JP", "KR"]
    assert filters["min_tmdb_score"] is None
    assert filters["min_tmdb_votes"] is None
    assert filters["_recommendation_collection"] == "new"
    assert filters["_recommendation_origin"] == "asia"
    assert intent["media_type"] == "tv"
    assert intent["countries"] == ["JP", "KR"]
    assert intent["release_preference"] == "new"
    assert intent["genre_groups"] == ["action_adventure"]


def test_simple_preferences_are_default_and_advanced_filters_remain_available(qtbot) -> None:
    _session, view = _build_view(qtbot, SimplePreferenceService(30))
    toggle = view.widget.findChild(QToolButton, "candidateRecommendationAdvancedModeToggle")
    advanced_section = view.widget.findChild(QWidget, "candidateFilterSection")

    assert toggle is not None and toggle.isChecked() is False
    assert advanced_section is not None and advanced_section.isHidden()
    assert view.widget.findChild(QComboBox, "candidateSearchMediaType") is not None
    simple_fields = view.widget.findChildren(QWidget, "candidateSimplePreferenceField")
    assert len(simple_fields) == 4
    assert all("background: transparent" in field.styleSheet() for field in simple_fields)
    toggle.setChecked(True)
    assert advanced_section.isHidden() is False


def test_simple_preferences_save_and_start_one_auto_refill(qtbot) -> None:
    from desktop.settings.recommendation_preferences import load_simple_recommendation_preferences

    service = SimplePreferenceService(1)
    _session, view = _build_view(qtbot, service)
    _set_combo(view, "simplePreferenceMedia", "movie")
    _set_combo(view, "simplePreferenceCollection", "classic")
    _set_combo(view, "simplePreferenceOrigin", "russia")
    _set_combo(view, "simplePreferenceMood", "dark")
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")

    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: len(service.replenish_calls) == 1)

    saved = load_simple_recommendation_preferences()
    assert saved.to_dict() == {
        "media": "movie",
        "collection": "classic",
        "origin": "russia",
        "mood": "dark",
    }
    assert service.replenish_calls[0]["countries"] == ["RU"]


def test_sufficient_local_pool_skips_network_refill(qtbot) -> None:
    service = SimplePreferenceService(30)
    session, view = _build_view(qtbot, service)
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")

    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: session.filters is not None)

    assert service.replenish_calls == []


def test_network_error_keeps_local_results(qtbot) -> None:
    service = SimplePreferenceService(1, replenish_ok=False)
    session, view = _build_view(qtbot, service)
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")

    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: view._last_replenish_result is not None)

    assert session.filtered_count == 1
    assert [item["title"] for item in session.sorted_candidates()] == ["Candidate 0"]


def test_second_refill_does_not_start_while_worker_is_active(qtbot, monkeypatch) -> None:
    import desktop.candidates.filters_view as module

    starts: list[dict] = []

    class Hook:
        def connect(self, _callback) -> None:
            return None

    class BlockingWorker:
        def __init__(self, intent, **_kwargs) -> None:
            self.intent = dict(intent)
            self.progress = Hook()
            self.finished_with_result = Hook()
            self.failed = Hook()
            self.finished = Hook()

        def start(self) -> None:
            starts.append(self.intent)

        def deleteLater(self) -> None:
            return None

    monkeypatch.setattr(module, "FilterReplenishWorker", BlockingWorker)
    _session, view = _build_view(qtbot, SimplePreferenceService(1))
    intent = {"target_add_count": 30}

    view._start_filter_replenish(intent)
    view._start_filter_replenish(intent)

    assert len(starts) == 1


def test_simple_summary_uses_human_readable_values(qtbot) -> None:
    _session, view = _build_view(qtbot, SimplePreferenceService(30))
    _set_combo(view, "simplePreferenceMedia", "tv")
    _set_combo(view, "simplePreferenceCollection", "unusual")
    _set_combo(view, "simplePreferenceOrigin", "asia")
    _set_combo(view, "simplePreferenceMood", "light")

    values = {key: label.text() for key, label in view._summary_value_labels.items() if label.isVisible()}
    assert set(values.values()) == {"Сериалы", "Необычное", "Азия", "Лёгкое"}


def test_simple_preference_copy_exists_in_ru_and_en() -> None:
    from desktop.i18n import translate

    keys = (
        "preferences.title",
        "preferences.media.label",
        "preferences.collection.unusual",
        "preferences.origin.asia",
        "preferences.mood.dynamic",
        "preferences.advanced.show",
    )
    for language in ("ru", "en"):
        assert all(translate(key, interface_language=language) != key for key in keys)


def test_unrated_candidate_formatter_uses_localized_unknown_label(monkeypatch) -> None:
    import desktop.candidates.presenters as presenters
    from desktop.i18n import translate

    candidate = {"tmdb_score": 0, "tmdb_votes": 0}
    monkeypatch.setattr(presenters, "tr", lambda key: translate(key, interface_language="ru"))
    assert presenters.format_candidate_metric_value(candidate, "tmdb_score") == "Оценок пока нет"
    monkeypatch.setattr(presenters, "tr", lambda key: translate(key, interface_language="en"))
    assert presenters.format_candidate_metric_value(candidate, "tmdb_votes") == "No ratings yet"
