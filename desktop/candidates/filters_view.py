"""Desktop Filters tab for runtime candidate pool filtering."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from candidates import service as candidate_service
from config import constant
from desktop.candidates.filters_controls import (
    KP_SCORE_SLIDER_MAX,
    KP_SCORE_SLIDER_STEP,
    VOTES_SLIDER_MAX_INDEX,
    VOTES_SLIDER_STEPS,
    min_score_from_slider,
    min_votes_from_slider,
    set_score_slider_from_default,
    set_votes_slider_from_default,
    update_score_range_label,
    update_votes_range_label,
)
from desktop.candidates.filters_form import CANDIDATE_YEAR_MIN, FiltersFormWidgets, build_filters_form
from desktop.candidates.filters_intro import build_intro_copy
from desktop.candidates.session import CandidateSearchSession, DEFAULT_BROWSE_FILTERS

APPLY_BUTTON_WIDTH_RATIO = 0.25
APPLY_BUTTON_HEIGHT = 32


class CandidateFiltersView:
    """Filters tab: configure runtime pool filters and apply."""

    def __init__(
        self,
        session: CandidateSearchSession,
        *,
        service=None,
        on_applied: Callable[[], None] | None = None,
    ) -> None:
        self._session = session
        self._service = service or session.service
        self._on_applied = on_applied
        self._genre_options: list[str] = []
        self._year_max = constant.NOW_YEAR

        view = self

        class CandidateFiltersRootWidget(QWidget):
            def resizeEvent(self, event) -> None:
                super().resizeEvent(event)
                view._update_apply_button_width()

        self._widget = CandidateFiltersRootWidget()
        self._widget.setObjectName("candidateFiltersRoot")
        root_layout = QVBoxLayout(self._widget)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        self._apply_button = QPushButton("Применить фильтры")
        self._apply_button.setObjectName("candidateSearchApplyTopButton")
        self._apply_button.clicked.connect(self._apply_filters)
        self._apply_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._apply_button.setFixedHeight(APPLY_BUTTON_HEIGHT)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(12)

        header = QLabel("Фильтры")
        header.setObjectName("candidateSearchHeader")
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_bar.addWidget(header, stretch=1)
        top_bar.addWidget(
            self._apply_button,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        root_layout.addLayout(top_bar)

        self._intro_card = QFrame()
        self._intro_card.setObjectName("candidateFiltersIntro")
        intro_layout = QVBoxLayout(self._intro_card)
        intro_layout.setContentsMargins(14, 12, 14, 12)
        intro_layout.setSpacing(6)

        self._intro_lead = QLabel(
            "Настройте условия ниже и нажмите «Применить фильтры». "
            "Список откроется на вкладке «Кандидаты»."
        )
        self._intro_lead.setObjectName("candidateFiltersIntroLead")
        self._intro_lead.setWordWrap(True)
        intro_layout.addWidget(self._intro_lead)

        self._intro_stats = QLabel("")
        self._intro_stats.setObjectName("candidateFiltersIntroStats")
        self._intro_stats.setWordWrap(True)
        intro_layout.addWidget(self._intro_stats)

        root_layout.addWidget(self._intro_card)

        self._form = build_filters_form(
            year_max=self._year_max,
            on_year_range_changed=self._on_year_range_changed,
        )
        root_layout.addWidget(self._form.scroll, stretch=1)

        self._update_apply_button_width()
        self._update_year_range_label()
        self._refresh_threshold_labels()
        self._apply_filter_defaults()
        self._update_intro()

    @property
    def widget(self) -> QWidget:
        return self._widget

    @property
    def _country_selector(self):
        return self._form.country_selector

    @property
    def _year_range_label(self):
        return self._form.year_range_label

    @property
    def _year_slider(self):
        return self._form.year_slider

    @property
    def _include_genre_selector(self):
        return self._form.include_genre_selector

    @property
    def _exclude_genre_selector(self):
        return self._form.exclude_genre_selector

    @property
    def _kp_score_slider(self):
        return self._form.kp_score_slider

    @property
    def _kp_score_range_label(self):
        return self._form.kp_score_range_label

    @property
    def _imdb_score_slider(self):
        return self._form.imdb_score_slider

    @property
    def _imdb_score_range_label(self):
        return self._form.imdb_score_range_label

    @property
    def _kp_votes_slider(self):
        return self._form.kp_votes_slider

    @property
    def _kp_votes_range_label(self):
        return self._form.kp_votes_range_label

    @property
    def _imdb_votes_slider(self):
        return self._form.imdb_votes_slider

    @property
    def _imdb_votes_range_label(self):
        return self._form.imdb_votes_range_label

    @property
    def _only_complete_check(self):
        return self._form.only_complete_check

    @property
    def _only_unwatched_check(self):
        return self._form.only_unwatched_check

    @property
    def _hide_hidden_check(self):
        return self._form.hide_hidden_check

    def _update_intro(self, *, result_count: int | None = None, result_ok: bool | None = None) -> None:
        overview = self._service.get_search_overview_view()
        lead, stats, apply_enabled = build_intro_copy(
            self._session,
            overview,
            result_count=result_count,
            result_ok=result_ok,
        )
        self._intro_lead.setText(lead)
        self._intro_stats.setText(stats)
        self._apply_button.setEnabled(apply_enabled)

    def _update_apply_button_width(self) -> None:
        width = self._widget.width()
        if width <= 0:
            return
        max_width = max(120, int(width * APPLY_BUTTON_WIDTH_RATIO))
        content_width = self._apply_button.sizeHint().width()
        target = min(max_width, content_width)
        self._apply_button.setFixedWidth(target)
        self._apply_button.setFixedHeight(APPLY_BUTTON_HEIGHT)

    def _on_year_range_changed(self, _lower: int, _upper: int) -> None:
        self._update_year_range_label()

    def _update_year_range_label(self) -> None:
        year_from, year_to = self._year_slider.values()
        self._year_range_label.setText(f"{year_from}–{year_to}")

    def _refresh_threshold_labels(self) -> None:
        update_score_range_label(self._kp_score_slider, self._kp_score_range_label)
        update_score_range_label(self._imdb_score_slider, self._imdb_score_range_label)
        update_votes_range_label(self._kp_votes_slider, self._kp_votes_range_label)
        update_votes_range_label(self._imdb_votes_slider, self._imdb_votes_range_label)

    def _set_year_slider_from_defaults(self, year_min, year_max) -> None:
        lower = CANDIDATE_YEAR_MIN
        upper = self._year_max
        if year_min not in (None, ""):
            try:
                lower = int(year_min)
            except (TypeError, ValueError):
                lower = CANDIDATE_YEAR_MIN
        if year_max not in (None, ""):
            try:
                upper = int(year_max)
            except (TypeError, ValueError):
                upper = self._year_max
        lower = max(CANDIDATE_YEAR_MIN, min(self._year_max, lower))
        upper = max(CANDIDATE_YEAR_MIN, min(self._year_max, upper))
        if lower > upper:
            lower, upper = upper, lower
        self._year_slider.blockSignals(True)
        self._year_slider.setValues(lower, upper)
        self._year_slider.blockSignals(False)
        self._update_year_range_label()

    def _year_filter_bounds(self) -> tuple[int | None, int | None]:
        year_from, year_to = self._year_slider.values()
        year_min = None if year_from <= CANDIDATE_YEAR_MIN else year_from
        year_max = None if year_to >= self._year_max else year_to
        return year_min, year_max

    def _apply_filter_defaults(self) -> None:
        defaults_view = self._service.get_search_filter_defaults_view()
        defaults = defaults_view.get("defaults") or {}
        chip_view = self._service.get_search_filter_chip_options_view()
        genre_labels = [
            str(item.get("label") or "").strip()
            for item in chip_view.get("genres") or []
            if str(item.get("label") or "").strip()
        ]
        self._genre_options = genre_labels
        self._include_genre_selector.set_options(genre_labels, defaults.get("include_genres") or [])
        self._exclude_genre_selector.set_options(genre_labels, defaults.get("exclude_genres") or [])

        country_options = [
            {"code": str(item.get("code") or "").strip(), "label": str(item.get("label") or "").strip()}
            for item in chip_view.get("countries") or []
            if str(item.get("code") or "").strip()
        ]
        self._country_selector.set_options(country_options, defaults.get("country"))

        self._set_year_slider_from_defaults(defaults.get("year_min"), defaults.get("year_max"))
        set_score_slider_from_default(self._kp_score_slider, defaults.get("min_kp_score"))
        set_score_slider_from_default(self._imdb_score_slider, defaults.get("min_imdb_score"))
        set_votes_slider_from_default(self._kp_votes_slider, defaults.get("min_kp_votes"))
        set_votes_slider_from_default(self._imdb_votes_slider, defaults.get("min_imdb_votes"))
        self._refresh_threshold_labels()
        self._only_complete_check.setChecked(DEFAULT_BROWSE_FILTERS["only_complete"])
        self._only_unwatched_check.setChecked(DEFAULT_BROWSE_FILTERS["only_unwatched"])
        self._hide_hidden_check.setChecked(DEFAULT_BROWSE_FILTERS["hide_hidden"])

    def _collect_filters(self) -> dict:
        countries = self._country_selector.selected_country_codes()
        year_min, year_max = self._year_filter_bounds()

        return {
            "criteria_name": None,
            "source": None,
            "country": countries,
            "year_min": year_min,
            "year_max": year_max,
            "include_genres": self._include_genre_selector.selected_genres(),
            "exclude_genres": self._exclude_genre_selector.selected_genres(),
            "min_kp_score": min_score_from_slider(self._kp_score_slider),
            "min_kp_votes": min_votes_from_slider(self._kp_votes_slider),
            "min_imdb_score": min_score_from_slider(self._imdb_score_slider),
            "min_imdb_votes": min_votes_from_slider(self._imdb_votes_slider),
            "only_complete": self._only_complete_check.isChecked(),
            "only_unwatched": self._only_unwatched_check.isChecked(),
            "hide_hidden": self._hide_hidden_check.isChecked(),
        }

    def _apply_filters(self) -> None:
        result = self._session.apply_filters(self._collect_filters())
        if result.get("is_empty_pool"):
            self._update_intro()
            return

        filtered_count = int(result.get("filtered_count", 0) or 0)
        self._update_intro(
            result_count=filtered_count,
            result_ok=filtered_count > 0,
        )

        if self._on_applied is not None:
            self._on_applied()
