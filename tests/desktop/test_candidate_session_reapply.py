from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QLabel, QPushButton

from desktop.candidates.filters_view import CandidateFiltersView
from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS


def _candidate(title: str, *, year: int = 2024, media_type: str = "movie") -> dict:
    return {
        "pool_entry_key": f"{title.casefold()}|{year}|{media_type}",
        "title": title,
        "year": year,
        "media_type": media_type,
        "is_searchable": True,
        "is_complete": True,
    }


class ReapplyService:
    SEARCH_SORT_MODES = ("final_score", "year", "relevance")
    SEARCH_SORT_MODE_LABELS = {
        "final_score": "Final",
        "year": "Year",
        "relevance": "Relevance",
    }

    def __init__(self) -> None:
        self.candidates = [_candidate("Alpha One", year=2023)]
        self.overview_calls = 0
        self.search_calls = 0
        self.text_queries: list[str] = []
        self.sort_modes: list[str] = []
        self.replenish_calls: list[dict] = []

    def get_search_overview_view(self) -> dict:
        self.overview_calls += 1
        return {
            "is_empty": len(self.candidates) == 0,
            "summary": f"{len(self.candidates)} candidates",
            "stats": {
                "storage_total": len(self.candidates),
                "unique_total": len(self.candidates),
                "ready_total": len(self.candidates),
                "incomplete_total": 0,
            },
            "candidates": deepcopy(self.candidates),
        }

    def search_candidate_pool(self, candidates: list[dict], filters: dict) -> dict:
        self.search_calls += 1
        media_type = filters.get("media_type")
        result = [
            candidate
            for candidate in candidates
            if media_type in (None, candidate.get("media_type"))
        ]
        return {"candidates": result, "filtered_count": len(result)}

    def search_candidate_pool_text(
        self,
        candidates: list[dict],
        filters: dict,
        *,
        text_query: str | None = None,
    ) -> dict:
        self.text_queries.append(str(text_query or ""))
        view = self.search_candidate_pool(candidates, filters)
        query = str(text_query or "").strip().casefold()
        if query == "":
            return view
        result = [
            candidate
            for candidate in view["candidates"]
            if query in str(candidate.get("title") or "").casefold()
        ]
        return {"candidates": result, "filtered_count": len(result)}

    def sort_search_candidates(self, candidates: list[dict], sort_mode: str) -> dict:
        self.sort_modes.append(sort_mode)
        return {"candidates": list(candidates), "sort_mode": sort_mode, "hidden_duplicates": 0}

    def get_search_filter_defaults_view(self) -> dict:
        return {"defaults": dict(DEFAULT_BROWSE_FILTERS)}

    def get_search_filter_chip_options_view(self) -> dict:
        return {"genres": [], "countries": [{"code": "US", "label": "United States"}]}

    def replenish_candidate_pool_for_filters(
        self,
        intent: dict,
        *,
        progress_callback=None,
        cancel_checker=None,
        dry_run: bool = False,
    ) -> dict:
        del progress_callback, cancel_checker, dry_run
        self.replenish_calls.append(dict(intent))
        self.candidates.append(_candidate("Alpha Two", year=2024))
        return {"ok": True, "requested_count": 30, "created_count": 1, "saved_count": 1}


def test_reload_from_pool_force_reapplies_once_and_preserves_query_sort() -> None:
    service = ReapplyService()
    session = CandidateSearchSession(service=service)
    filters = {**DEFAULT_BROWSE_FILTERS, "media_type": "movie"}
    session.set_sort_mode("year")

    session.apply_filters(filters, text_query="Alpha")
    service.candidates.append(_candidate("Alpha Two", year=2024))
    result = session.reload_from_pool(force=True)

    assert result["reapplied"] is True
    assert result["local_count_before"] == 1
    assert result["visible_count"] == 2
    assert service.overview_calls == 2
    assert service.search_calls == 2
    assert service.text_queries == ["Alpha", "Alpha"]
    assert service.sort_modes == ["year", "year"]
    assert session.sort_mode == "year"


def test_replenish_gui_reloads_pool_and_reapplies_without_loop(qtbot) -> None:
    service = ReapplyService()
    session = CandidateSearchSession(service=service)
    view = CandidateFiltersView(session, service=service)
    view._form.advanced_mode_toggle.setChecked(True)
    qtbot.addWidget(view.widget)
    view.widget.show()

    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    checkbox = view.widget.findChild(QCheckBox, "candidateReplenishEnabled")
    stats = view.widget.findChild(QLabel, "candidateFiltersIntroStats")
    assert apply_button is not None
    assert checkbox is not None
    assert stats is not None

    checkbox.setChecked(True)
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: len(service.replenish_calls) == 1)
    qtbot.waitUntil(lambda: view._last_replenish_result is not None and view._is_replenishing is False)

    assert service.search_calls == 2
    assert session.filtered_count == 2
    assert "Before: 1" in stats.text()
    assert "Added 1 of 30" in stats.text()
    assert "Visible now: 2" in stats.text()
