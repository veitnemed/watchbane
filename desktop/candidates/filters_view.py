"""Desktop Filters tab for runtime candidate pool filtering."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from candidates import service as candidate_service
from config import constant
from desktop.candidates.filters_controls import (
    SCORE_SLIDER_MAX,
    SCORE_SLIDER_STEP,
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
from desktop.theme.scaling import control_px, layout_px
from desktop.theme.shell_layout import (
    CANDIDATE_ROOT_MARGIN_PX,
    CANDIDATE_ROOT_SPACING_PX,
    LEFT_PANEL_TOP_COMPENSATION_PX,
)

APPLY_BUTTON_WIDTH_RATIO = 0.25
APPLY_BUTTON_HEIGHT = control_px(32)


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
        root_layout.setContentsMargins(
            CANDIDATE_ROOT_MARGIN_PX,
            CANDIDATE_ROOT_MARGIN_PX + LEFT_PANEL_TOP_COMPENSATION_PX,
            CANDIDATE_ROOT_MARGIN_PX,
            CANDIDATE_ROOT_MARGIN_PX,
        )
        root_layout.setSpacing(CANDIDATE_ROOT_SPACING_PX)

        self._apply_button = QPushButton("Применить фильтры")
        self._apply_button.setObjectName("candidateSearchApplyTopButton")
        self._apply_button.clicked.connect(self._apply_filters)
        self._apply_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._apply_button.setFixedHeight(APPLY_BUTTON_HEIGHT)

        self._reset_button = QPushButton("Сброс")
        self._reset_button.setObjectName("candidateSearchResetTopButton")
        self._reset_button.clicked.connect(self._reset_filters)
        self._reset_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._reset_button.setFixedHeight(APPLY_BUTTON_HEIGHT)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(CANDIDATE_ROOT_SPACING_PX)

        header = QLabel("Фильтры")
        header.setObjectName("candidateSearchHeader")
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_bar.addWidget(header, stretch=1)
        top_bar.addWidget(
            self._reset_button,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        top_bar.addWidget(
            self._apply_button,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        root_layout.addLayout(top_bar)

        self._intro_card = QFrame()
        self._intro_card.setObjectName("candidateFiltersIntro")
        intro_layout = QVBoxLayout(self._intro_card)
        intro_layout.setContentsMargins(
            layout_px(14),
            layout_px(12),
            layout_px(14),
            layout_px(12),
        )
        intro_layout.setSpacing(layout_px(6))

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
        session.add_listener(self._on_session_updated)
        session.add_loading_listener(self._on_loading_changed)
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
    def _tmdb_score_slider(self):
        return self._form.tmdb_score_slider

    @property
    def _tmdb_score_range_label(self):
        return self._form.tmdb_score_range_label

    @property
    def _tmdb_votes_slider(self):
        return self._form.tmdb_votes_slider

    @property
    def _tmdb_votes_range_label(self):
        return self._form.tmdb_votes_range_label

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
        overview = self._session.overview()
        lead, stats, apply_enabled = build_intro_copy(
            self._session,
            overview,
            result_count=result_count,
            result_ok=result_ok,
        )
        self._intro_lead.setText(lead)
        self._intro_stats.setText(stats)
        self._apply_button.setEnabled(apply_enabled and self._session.is_loading is False)
        self._reset_button.setEnabled(apply_enabled and self._session.is_loading is False)

    def _on_loading_changed(self) -> None:
        if self._session.is_loading:
            self._apply_button.setEnabled(False)
            self._reset_button.setEnabled(False)
            self._intro_lead.setText("Применяю фильтры...")
            self._intro_stats.setText("Окно можно не трогать, результат появится на вкладке «Кандидаты».")

    def _on_session_updated(self) -> None:
        if self._session.is_loading:
            return
        if self._session.last_error:
            self._intro_lead.setText("Не удалось применить фильтры.")
            self._intro_stats.setText(self._session.last_error)
            self._apply_button.setEnabled(True)
            self._reset_button.setEnabled(True)
            return
        if self._session.has_results:
            self._update_intro(
                result_count=self._session.filtered_count,
                result_ok=self._session.filtered_count > 0,
            )

    def _update_apply_button_width(self) -> None:
        width = self._widget.width()
        if width <= 0:
            return
        max_width = max(120, int(width * APPLY_BUTTON_WIDTH_RATIO))
        content_width = self._apply_button.sizeHint().width()
        target = min(max_width, content_width)
        self._apply_button.setFixedWidth(target)
        self._apply_button.setFixedHeight(APPLY_BUTTON_HEIGHT)
        self._reset_button.setFixedHeight(APPLY_BUTTON_HEIGHT)

    def _on_year_range_changed(self, _lower: int, _upper: int) -> None:
        self._update_year_range_label()

    def _update_year_range_label(self) -> None:
        year_from, year_to = self._year_slider.values()
        self._year_range_label.setText(f"{year_from}–{year_to}")

    def _refresh_threshold_labels(self) -> None:
        update_score_range_label(self._tmdb_score_slider, self._tmdb_score_range_label)
        update_votes_range_label(self._tmdb_votes_slider, self._tmdb_votes_range_label)

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
        set_score_slider_from_default(self._tmdb_score_slider, defaults.get("min_tmdb_score"))
        set_votes_slider_from_default(self._tmdb_votes_slider, defaults.get("min_tmdb_votes"))
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
            "min_tmdb_score": min_score_from_slider(self._tmdb_score_slider),
            "min_tmdb_votes": min_votes_from_slider(self._tmdb_votes_slider),
            "only_complete": self._only_complete_check.isChecked(),
            "only_unwatched": self._only_unwatched_check.isChecked(),
            "hide_hidden": self._hide_hidden_check.isChecked(),
        }

    def _clear_filter_controls(self) -> None:
        self._country_selector.clear_selection()
        self._include_genre_selector.clear_selection()
        self._exclude_genre_selector.clear_selection()
        self._set_year_slider_from_defaults(None, None)
        set_score_slider_from_default(self._tmdb_score_slider, None)
        set_votes_slider_from_default(self._tmdb_votes_slider, None)
        self._refresh_threshold_labels()
        self._only_complete_check.setChecked(False)
        self._only_unwatched_check.setChecked(False)
        self._hide_hidden_check.setChecked(False)

    def _reset_filters(self) -> None:
        self._clear_filter_controls()
        self._apply_filters()

    def _apply_filters(self) -> None:
        self._session.apply_filters_async(self._collect_filters(), parent=self._widget)

        if self._on_applied is not None:
            self._on_applied()
