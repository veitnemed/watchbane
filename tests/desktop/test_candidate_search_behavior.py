from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QListWidget, QPushButton, QCheckBox

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
        "kp_score": None,
        "kp_votes": None,
        "imdb_score": None,
        "imdb_votes": None,
        "overview": "Can be searched before prediction data is ready.",
    }


def _predict_ready_candidate() -> dict:
    return {
        "pool_entry_key": "predict-ready|2023",
        "title": "Predict Ready",
        "year": 2023,
        "is_searchable": True,
        "is_complete": True,
        "kp_score": 8.1,
        "kp_votes": 10000,
        "imdb_score": 7.7,
        "imdb_votes": 2000,
        "overview": "Has enough scores for prediction-ready mode.",
    }


class FakeCandidateService:
    SEARCH_SORT_MODES = ("kp_score", "imdb_score", "kp_votes", "imdb_votes")
    SEARCH_SORT_MODE_LABELS = {
        "kp_score": "KP",
        "imdb_score": "IMDb",
        "kp_votes": "KP votes",
        "imdb_votes": "IMDb votes",
    }

    def __init__(self, candidates: list[dict] | None = None) -> None:
        self.candidates = deepcopy(candidates or [_searchable_candidate(), _predict_ready_candidate()])
        self.hidden_candidates: list[dict] = []
        self.applied_filters: list[dict] = []

    def get_search_overview_view(self) -> dict:
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
            if filters.get("hide_hidden") and candidate_detail_identity(candidate) in hidden:
                continue
            if filters.get("only_complete") and candidate.get("is_complete") is not True:
                continue
            filtered.append(candidate)
        return {"candidates": filtered, "filtered_count": len(filtered)}

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
        return {"genres": [], "countries": []}

    def hide_candidate(self, candidate: dict) -> dict:
        self.hidden_candidates.append(deepcopy(candidate))
        return {"ok": True, "hidden": True}


def _build_views(qtbot, service: FakeCandidateService | None = None):
    service = service or FakeCandidateService()
    session = CandidateSearchSession(service=service)
    filters_view = CandidateFiltersView(session, service=service)
    list_view = CandidateListView(session, service=service)
    qtbot.addWidget(filters_view.widget)
    qtbot.addWidget(list_view.widget)
    filters_view.widget.show()
    list_view.widget.show()
    return service, session, filters_view, list_view


def _candidate_list(list_view: CandidateListView) -> QListWidget:
    widget = list_view.widget.findChild(QListWidget, "candidateListWidget")
    assert widget is not None
    return widget


def _listed_titles(list_widget: QListWidget) -> list[str]:
    titles = []
    for index in range(list_widget.count()):
        candidate = list_widget.item(index).data(Qt.ItemDataRole.UserRole)
        titles.append(candidate.get("title"))
    return titles


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
    qtbot.waitUntil(lambda: list_widget.count() == 1)
    assert _listed_titles(list_widget) == ["Predict Ready"]


def test_selecting_candidate_row_updates_detail_card_and_missing_poster_placeholder(qtbot) -> None:
    _service, session, _filters_view, list_view = _build_views(qtbot)
    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: list_widget.count() == 2)

    row = _listed_titles(list_widget).index("Searchable Only")
    list_widget.setCurrentRow(row)

    title_label = list_view.widget.findChild(QLabel, "detailTitle")
    poster_label = list_view.widget.findChild(QLabel, "detailPoster")
    assert title_label is not None
    assert poster_label is not None
    qtbot.waitUntil(lambda: "Searchable Only" in title_label.text())
    assert poster_label.text() == "Нет постера"


def test_hide_button_calls_service_and_removes_candidate_row(qtbot) -> None:
    service, session, _filters_view, list_view = _build_views(qtbot)
    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: list_widget.count() == 2)
    list_widget.setCurrentRow(_listed_titles(list_widget).index("Searchable Only"))

    hide_button = list_view.widget.findChild(QPushButton, "candidateHideButton")
    assert hide_button is not None
    qtbot.waitUntil(lambda: hide_button.isEnabled())
    qtbot.mouseClick(hide_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: list_widget.count() == 1)
    assert [candidate["title"] for candidate in service.hidden_candidates] == ["Searchable Only"]
    assert _listed_titles(list_widget) == ["Predict Ready"]


def test_filter_change_updates_candidate_list(qtbot) -> None:
    _service, _session, filters_view, list_view = _build_views(qtbot)
    list_widget = _candidate_list(list_view)
    apply_button = filters_view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    only_complete = filters_view.widget.findChild(QCheckBox, "candidateSearchOnlyComplete")
    assert apply_button is not None
    assert only_complete is not None

    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: list_widget.count() == 2)
    assert _listed_titles(list_widget) == ["Predict Ready", "Searchable Only"]

    only_complete.setChecked(True)
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: list_widget.count() == 1)
    assert _listed_titles(list_widget) == ["Predict Ready"]
