from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QComboBox, QProgressBar, QPushButton

from desktop.candidates.filters_view import CandidateFiltersView, clamp_filter_replenish_batch_size
from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS
from desktop.i18n import tr


class FakeReplenishService:
    SEARCH_SORT_MODES = ("final_score",)
    SEARCH_SORT_MODE_LABELS = {"final_score": "Final"}

    def __init__(
        self,
        replenish_result: dict | None = None,
        *,
        country_options: list[dict] | None = None,
    ) -> None:
        self.candidates = [
            {
                "pool_entry_key": "alpha|2024|movie",
                "title": "Alpha",
                "year": 2024,
                "media_type": "movie",
                "country_codes": ["US"],
                "is_searchable": True,
                "is_complete": True,
            }
        ]
        self.replenish_result = replenish_result or {
            "ok": True,
            "requested_count": 30,
            "created_count": 3,
            "saved_count": 3,
        }
        self.replenish_calls: list[dict] = []
        self.overview_calls = 0
        self.search_calls: list[dict] = []
        self.country_options = country_options or [
            {"code": "RU", "label": "Russia"},
            {"code": "JP", "label": "Japan"},
            {"code": "KR", "label": "Korea"},
        ]

    def get_search_overview_view(self) -> dict:
        self.overview_calls += 1
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
        self.search_calls.append(dict(filters))
        media_type = filters.get("media_type")
        countries = {str(code).strip().upper() for code in filters.get("country") or [] if str(code).strip()}
        result = [
            candidate
            for candidate in candidates
            if media_type in (None, candidate.get("media_type"))
            and (
                not countries
                or bool(countries.intersection(str(code).strip().upper() for code in candidate.get("country_codes") or []))
            )
        ]
        return {"candidates": result, "filtered_count": len(result)}

    def sort_search_candidates(self, candidates: list[dict], sort_mode: str) -> dict:
        return {"candidates": list(candidates), "sort_mode": sort_mode, "hidden_duplicates": 0}

    def get_search_filter_defaults_view(self) -> dict:
        return {"defaults": dict(DEFAULT_BROWSE_FILTERS)}

    def get_search_filter_chip_options_view(self) -> dict:
        return {
            "genres": [{"label": "Drama"}],
            "countries": list(self.country_options),
        }

    def replenish_candidate_pool_for_filters(
        self,
        intent: dict,
        *,
        progress_callback=None,
        cancel_checker=None,
        dry_run: bool = False,
    ) -> dict:
        del cancel_checker, dry_run
        self.replenish_calls.append(dict(intent))
        if progress_callback is not None:
            progress_callback({
                "bucket_id": "RU:tv:1",
                "page": 1,
                "accepted_count": 1,
                "selected_count": 1,
                "target_count": 30,
                "stage": "accepted",
            })
        return dict(self.replenish_result)


def _build_view(qtbot, service: FakeReplenishService | None = None):
    service = service or FakeReplenishService()
    session = CandidateSearchSession(service=service)
    view = CandidateFiltersView(session, service=service)
    view._form.advanced_mode_toggle.setChecked(True)
    qtbot.addWidget(view.widget)
    view.widget.show()
    return service, session, view


def test_default_candidate_search_service_exposes_filter_replenish() -> None:
    session = CandidateSearchSession()

    assert callable(getattr(session.service, "replenish_candidate_pool_for_filters", None))


def test_filter_layout_stacks_without_hidden_horizontal_overflow(qtbot) -> None:
    _service, _session, view = _build_view(qtbot)

    view.widget.resize(900, 700)
    qtbot.waitUntil(lambda: view._content_stacked is True)

    assert abs(view._form.scroll.width() - view._summary_scroll.width()) <= 4

    view.widget.resize(1280, 700)
    qtbot.waitUntil(lambda: view._content_stacked is False)

    assert view._form.scroll.width() > view._summary_scroll.width()


def test_filter_intro_stats_are_visible_when_copy_is_nonempty(qtbot) -> None:
    _service, _session, view = _build_view(qtbot)

    assert view._intro_stats.text().strip()
    assert view._intro_stats.isVisible()


def test_filter_state_refreshes_when_pool_becomes_empty(qtbot) -> None:
    _service, session, view = _build_view(qtbot)
    session.last_error = "previous failure"
    session.filters = dict(DEFAULT_BROWSE_FILTERS)
    session.filtered_candidates = [{"title": "Before"}]
    session.filtered_count = 1
    session._notify_listeners()

    session._apply_search_result(
        dict(DEFAULT_BROWSE_FILTERS),
        {
            "is_empty_pool": True,
            "overview": {"is_empty": True, "candidates": [], "stats": {}},
        },
    )

    assert view._intro_lead.text() == tr("candidates.filters.empty.lead")
    assert view._intro_stats.text() == tr("candidates.filters.empty.stats")
    assert view._intro_stats.isVisible()
    assert view._apply_button.isEnabled() is False
    assert session.last_error is None


def test_filter_error_hides_raw_service_details(qtbot) -> None:
    _service, session, view = _build_view(qtbot)
    raw_error = "token=secret-token path D:\\runtime\\watchbane.sqlite3"

    session.last_error = raw_error
    session._notify_listeners()

    assert view._intro_lead.text() == tr("candidates.filters.error.lead")
    assert view._intro_stats.text() == tr("candidates.filters.error.stats")
    assert raw_error not in view._intro_stats.text()


def test_async_error_does_not_retry_failed_overview_on_ui_thread(qtbot) -> None:
    _service, session, view = _build_view(qtbot)

    class BrokenOverviewService:
        calls = 0

        def get_search_overview_view(self):
            self.calls += 1
            raise RuntimeError("database unavailable")

    broken = BrokenOverviewService()
    session.service = broken
    session._overview_cache = None
    session._request_id = 1
    session._set_loading(True)

    session._on_async_result(
        1,
        dict(DEFAULT_BROWSE_FILTERS),
        {
            "ok": False,
            "is_empty_pool": False,
            "error": "database unavailable",
            "candidates": [],
        },
    )

    assert broken.calls == 0
    assert session.is_loading is False
    assert session.last_error == "database unavailable"
    assert view._intro_stats.text() == tr("candidates.filters.error.stats")


def test_summary_sidebar_yields_width_to_filters_on_narrow_window(qtbot) -> None:
    _service, _session, view = _build_view(qtbot)
    view.widget.resize(1100, 800)
    qtbot.waitUntil(lambda: view._intro_card.width() < 400)

    assert view._intro_card.width() <= int(view.widget.width() * 0.35)


def test_apply_with_replenish_unchecked_keeps_old_behavior(qtbot) -> None:
    service, _session, view = _build_view(qtbot)
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    checkbox = view.widget.findChild(QCheckBox, "candidateReplenishEnabled")
    progress = view.widget.findChild(QProgressBar, "candidateReplenishProgressBar")
    assert apply_button is not None
    assert checkbox is not None
    assert progress is not None
    assert checkbox.isChecked() is False

    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: service.overview_calls >= 1)

    assert service.replenish_calls == []
    assert progress.isHidden() is True


def test_apply_with_replenish_checked_calls_worker_service_seam(qtbot) -> None:
    service, session, view = _build_view(qtbot)
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    checkbox = view.widget.findChild(QCheckBox, "candidateReplenishEnabled")
    media_combo = view.widget.findChild(QComboBox, "candidateSearchMediaType")
    progress = view.widget.findChild(QProgressBar, "candidateReplenishProgressBar")
    assert apply_button is not None
    assert checkbox is not None
    assert media_combo is not None
    assert progress is not None

    view._form.discovery_media_control.setValue("movie")
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: len(service.replenish_calls) == 1)
    qtbot.waitUntil(lambda: view._last_replenish_result is not None)

    intent = service.replenish_calls[0]
    assert intent["media_type"] == "movie"
    assert intent["target_add_count"] == 30
    assert intent["allow_advanced_override"] is False
    assert view._last_replenish_result["saved_count"] == 3
    assert session.filters is not None
    assert progress.isVisible() is True
    assert progress.maximum() == 30
    assert progress.value() == 3
    assert progress.text() == "3 / 30"


def test_preset_country_filters_even_when_country_chip_is_absent(qtbot) -> None:
    service, session, view = _build_view(
        qtbot,
        FakeReplenishService(country_options=[{"code": "US", "label": "United States"}]),
    )
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    direction = view._form.direction_control
    assert apply_button is not None
    assert direction is not None

    values = direction.property("directionValues")
    direction.setValue(values.index("russian_mainstream"))
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: len(service.search_calls) == 1)

    assert service.search_calls[0]["country"] == ["RU"]
    assert session.filtered_count == 0
    assert session.sorted_candidates() == []


def test_apply_with_blocked_replenish_result_keeps_local_results(qtbot) -> None:
    service, session, view = _build_view(
        qtbot,
        FakeReplenishService(
            {
                "ok": False,
                "blocked": True,
                "requested_count": 30,
                "created_count": 0,
                "saved_count": 0,
            }
        ),
    )
    apply_button = view.widget.findChild(QPushButton, "candidateSearchApplyTopButton")
    checkbox = view.widget.findChild(QCheckBox, "candidateReplenishEnabled")
    progress = view.widget.findChild(QProgressBar, "candidateReplenishProgressBar")
    assert apply_button is not None
    assert checkbox is not None
    assert progress is not None

    checkbox.setChecked(True)
    qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: len(service.replenish_calls) == 1)
    qtbot.waitUntil(lambda: view._last_replenish_result is not None)

    assert view._last_replenish_result["blocked"] is True
    assert session.filters is not None
    assert progress.isHidden() is True


def test_replenish_batch_size_is_clamped_to_30() -> None:
    assert clamp_filter_replenish_batch_size(30) == 30
    assert clamp_filter_replenish_batch_size(999) == 30
    assert clamp_filter_replenish_batch_size("bad") == 30
    assert clamp_filter_replenish_batch_size(0) == 1
