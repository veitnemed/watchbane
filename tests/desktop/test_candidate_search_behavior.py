from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QListView, QPushButton, QCheckBox, QComboBox

from desktop.candidates.list_model import CandidateListModel, CandidateListRoles
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
    SEARCH_SORT_MODES = ("final_score", "quality_score", "tmdb_score", "tmdb_votes", "tmdb_popularity", "year")
    SEARCH_SORT_MODE_LABELS = {
        "final_score": "Итог",
        "quality_score": "Качество",
        "tmdb_score": "TMDb",
        "tmdb_votes": "Голоса TMDb",
        "tmdb_popularity": "Популярность TMDb",
        "year": "Год",
    }

    def __init__(self, candidates: list[dict] | None = None) -> None:
        self.candidates = deepcopy(candidates or [_searchable_candidate(), _predict_ready_candidate()])
        self.hidden_candidates: list[dict] = []
        self.applied_filters: list[dict] = []
        self.overview_calls = 0
        self.chip_options = {"genres": [], "countries": []}

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


def _build_views(qtbot, service: FakeCandidateService | None = None):
    service = service or FakeCandidateService()
    session = CandidateSearchSession(service=service)
    filters_view = CandidateFiltersView(session, service=service)
    list_view = CandidateListView(session, service=service)
    list_widget = list_view.widget.findChild(QListView, "candidateListWidget")
    assert list_widget is not None
    list_widget.setUpdatesEnabled(False)
    qtbot.addWidget(filters_view.widget)
    qtbot.addWidget(list_view.widget)
    filters_view.widget.show()
    list_view.widget.show()
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


def test_hide_button_calls_service_and_removes_candidate_row(qtbot) -> None:
    service, session, _filters_view, list_view = _build_views(qtbot)
    session.apply_filters({**DEFAULT_BROWSE_FILTERS, "only_complete": False})
    list_widget = _candidate_list(list_view)
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 2)
    list_widget.setCurrentIndex(list_widget.model().index(_listed_titles(list_widget).index("Searchable Only"), 0))

    hide_button = list_view.widget.findChild(QPushButton, "candidateHideButton")
    assert hide_button is not None
    qtbot.waitUntil(lambda: hide_button.isEnabled())
    qtbot.mouseClick(hide_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: _listed_count(list_widget) == 1)
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
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 2)
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

    media_type_combo.setCurrentIndex(media_type_combo.findData("movie"))
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: _listed_titles(list_widget) == ["Ready Movie"])
    assert service.applied_filters[-1]["media_type"] == "movie"


def test_filter_reset_button_clears_and_applies_all_filters(qtbot) -> None:
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
    qtbot.waitUntil(lambda: _listed_count(list_widget) == 2)

    assert only_complete.isChecked() is False
    assert only_unwatched.isChecked() is False
    assert service.applied_filters[-1] == {
        **DEFAULT_BROWSE_FILTERS,
        "only_unwatched": False,
    }
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
