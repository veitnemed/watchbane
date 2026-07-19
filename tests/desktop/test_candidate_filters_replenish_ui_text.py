from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QLabel, QPushButton

from desktop.candidates.filters_form import build_filters_form
from desktop.candidates.filters_view import CandidateFiltersView
from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS
from desktop.i18n import tr


class UiTextService:
    SEARCH_SORT_MODES = ("final_score",)
    SEARCH_SORT_MODE_LABELS = {"final_score": "Final"}

    def __init__(self, replenish_result: dict | None = None, *, add_on_replenish: bool = False) -> None:
        self.candidates = [
            {
                "pool_entry_key": "alpha|2024|movie",
                "title": "Alpha",
                "year": 2024,
                "media_type": "movie",
                "is_searchable": True,
                "is_complete": True,
            }
        ]
        self.replenish_result = replenish_result or {
            "ok": True,
            "requested_count": 30,
            "created_count": 1,
            "saved_count": 1,
        }
        self.add_on_replenish = add_on_replenish
        self.replenish_calls: list[dict] = []

    def get_search_overview_view(self) -> dict:
        return {
            "is_empty": False,
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
        del filters
        return {"candidates": list(candidates), "filtered_count": len(candidates)}

    def sort_search_candidates(self, candidates: list[dict], sort_mode: str) -> dict:
        return {"candidates": list(candidates), "sort_mode": sort_mode, "hidden_duplicates": 0}

    def get_search_filter_defaults_view(self) -> dict:
        return {"defaults": dict(DEFAULT_BROWSE_FILTERS)}

    def get_search_filter_chip_options_view(self) -> dict:
        return {"genres": [], "countries": [{"code": "JP", "label": "Japan"}]}

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
        if self.add_on_replenish:
            self.candidates.append(
                {
                    "pool_entry_key": "beta|2025|movie",
                    "title": "Beta",
                    "year": 2025,
                    "media_type": "movie",
                    "is_searchable": True,
                    "is_complete": True,
                }
            )
        return dict(self.replenish_result)


def _build_view(
    qtbot,
    service: UiTextService | None = None,
    *,
    on_replenish_state_changed=None,
):
    service = service or UiTextService()
    session = CandidateSearchSession(service=service)
    view = CandidateFiltersView(
        session,
        service=service,
        on_replenish_state_changed=on_replenish_state_changed,
    )
    view._form.advanced_mode_toggle.setChecked(True)
    qtbot.addWidget(view.widget)
    view.widget.show()
    return service, session, view


def test_replenish_form_explains_origin_animation_and_advanced_override(qtbot) -> None:
    form = build_filters_form(year_max=2026, on_year_range_changed=lambda _low, _high: None)
    qtbot.addWidget(form.scroll)

    hint_text = "\n".join(label.text() for label in form.scroll.findChildren(QLabel, "candidateSearchHint"))

    assert tr("candidates.filters.country_hint") in hint_text
    assert tr("candidates.filters.replenish.hint.anime") in hint_text
    assert tr("candidates.filters.replenish.hint.live_action") in hint_text
    assert tr("candidates.filters.replenish.hint.advanced_override") in hint_text


def test_apply_without_replenish_reports_local_filter_applied(qtbot) -> None:
    service = UiTextService()
    service.candidates = [
        {**service.candidates[0], "pool_entry_key": f"alpha-{index}|2024|movie", "title": f"Alpha {index}"}
        for index in range(50)
    ]
    _service, _session, view = _build_view(qtbot, service)
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    lead = view.widget.findChild(QLabel, "candidateFiltersIntroLead")
    checkbox = view.widget.findChild(QCheckBox, "candidateReplenishEnabled")
    assert apply_button is not None
    assert lead is not None
    assert checkbox is not None

    checkbox.setChecked(False)
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: lead.text() == tr("recommendations.discovery.status.local_applied"))


def test_blocked_replenish_reports_no_tmdb_call_status(qtbot) -> None:
    states: list[str] = []
    service, _session, view = _build_view(
        qtbot,
        UiTextService(
            {
                "ok": False,
                "blocked": True,
                "requested_count": 30,
                "created_count": 0,
                "saved_count": 0,
            }
        ),
        on_replenish_state_changed=states.append,
    )
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    checkbox = view.widget.findChild(QCheckBox, "candidateReplenishEnabled")
    lead = view.widget.findChild(QLabel, "candidateFiltersIntroLead")
    assert apply_button is not None
    assert checkbox is not None
    assert lead is not None

    checkbox.setChecked(True)
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: len(service.replenish_calls) == 1)
    qtbot.waitUntil(lambda: lead.text() == tr("recommendations.discovery.status.conflict"))
    assert states == ["loading", "error"]


def test_underfilled_replenish_reports_added_count(qtbot) -> None:
    states: list[str] = []
    service, _session, view = _build_view(
        qtbot,
        UiTextService(add_on_replenish=True),
        on_replenish_state_changed=states.append,
    )
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    checkbox = view.widget.findChild(QCheckBox, "candidateReplenishEnabled")
    stats = view.widget.findChild(QLabel, "candidateFiltersIntroStats")
    assert apply_button is not None
    assert checkbox is not None
    assert stats is not None

    checkbox.setChecked(True)
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: len(service.replenish_calls) == 1)
    qtbot.waitUntil(
        lambda: tr(
            "recommendations.discovery.status.complete_partial",
            before=1,
            added=1,
            requested=30,
            visible=2,
        )
        in stats.text()
        or "Добавили 1 из 30" in stats.text()
    )
    assert states == ["loading", "finished"]
