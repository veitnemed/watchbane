"""Desktop Filters tab for runtime candidate pool filtering."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from candidates import service as candidate_service
from candidates.models import country_schema, genre_schema
from candidates.replenish.filter_intent import FilterReplenishIntent
from config import constant
from dataset.language import choose_genre_labels
from desktop.candidates.filter_icon_assets import filter_icon, filter_icon_label
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
from desktop.candidates.workers.filter_replenish_worker import FilterReplenishWorker
from desktop.i18n import tr
from desktop.settings.app_settings import get_persisted_data_language, get_persisted_interface_language
from desktop.theme.scaling import control_px, get_ui_scale, layout_px
from desktop.theme.shell_layout import (
    CANDIDATE_ROOT_MARGIN_PX,
    CANDIDATE_ROOT_SPACING_PX,
    LEFT_PANEL_TOP_COMPENSATION_PX,
)

APPLY_BUTTON_HEIGHT = control_px(40)
SUMMARY_CARD_WIDTH = layout_px(292 if get_ui_scale() >= 1.25 else 324)
FILTER_REPLENISH_DEFAULT_BATCH_SIZE = 30
FILTER_REPLENISH_MAX_BATCH_SIZE = 30


def clamp_filter_replenish_batch_size(value) -> int:
    """Return the safe per-apply replenish batch size."""
    try:
        requested = int(value)
    except (TypeError, ValueError):
        requested = FILTER_REPLENISH_DEFAULT_BATCH_SIZE
    return max(1, min(FILTER_REPLENISH_MAX_BATCH_SIZE, requested))


def _genre_labels_for_language(labels, data_language: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for label in labels or []:
        text = str(label or "").strip()
        if text == "":
            continue
        keys = genre_schema.normalize_genre_filter_list([text])
        localized_labels = choose_genre_labels(keys, data_language) or [text]
        for localized in localized_labels:
            localized = str(localized or "").strip()
            if localized == "" or localized.casefold() in seen:
                continue
            seen.add(localized.casefold())
            result.append(localized)
    return result


class CandidateFiltersView:
    """Filters tab: configure runtime pool filters and apply."""

    def __init__(
        self,
        session: CandidateSearchSession,
        *,
        service=None,
        on_applied: Callable[[], None] | None = None,
        on_before_apply: Callable[[dict], dict] | None = None,
    ) -> None:
        self._session = session
        self._service = service or session.service
        self._on_applied = on_applied
        self._on_before_apply = on_before_apply
        self._interface_language = get_persisted_interface_language()
        self._data_language = get_persisted_data_language()
        self._genre_options: list[str] = []
        self._year_max = constant.NOW_YEAR
        self._is_replenishing = False
        self._replenish_worker: FilterReplenishWorker | None = None
        self._last_replenish_result: dict | None = None
        self._pending_replenish_intent: dict | None = None
        self._replenish_local_count_before: int | None = None
        self._local_apply_requested = False

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

        self._apply_button = QPushButton(tr("candidates.filters.summary.apply"))
        self._apply_button.setObjectName("candidateSearchApplyTopButton")
        self._apply_button.setIcon(filter_icon("search", control_px(18), "#F5F7FB"))
        self._apply_button.setIconSize(QSize(control_px(18), control_px(18)))
        self._apply_button.clicked.connect(self._apply_filters)
        self._apply_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply_button.setFixedHeight(APPLY_BUTTON_HEIGHT)

        self._reset_button = QPushButton(tr("candidates.filters.summary.reset"))
        self._reset_button.setObjectName("candidateSearchResetTopButton")
        self._reset_button.setIcon(filter_icon("refresh", control_px(17), "#F5F7FB"))
        self._reset_button.setIconSize(QSize(control_px(17), control_px(17)))
        self._reset_button.clicked.connect(self._reset_filters)
        self._reset_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._reset_button.setFixedHeight(APPLY_BUTTON_HEIGHT)

        header_block = QVBoxLayout()
        header_block.setContentsMargins(0, 0, 0, 0)
        header_block.setSpacing(layout_px(4))

        header = QLabel(tr("candidates.filters.header"))
        header.setObjectName("candidateSearchHeader")
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header_block.addWidget(header)

        subtitle = QLabel(tr("candidates.filters.subtitle"))
        subtitle.setObjectName("candidateSearchSubtitle")
        subtitle.setWordWrap(True)
        header_block.addWidget(subtitle)

        root_layout.addLayout(header_block)

        self._intro_card = QFrame()
        self._intro_card.setObjectName("candidateFiltersIntro")
        self._intro_card.setFixedWidth(SUMMARY_CARD_WIDTH)
        self._intro_card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)
        intro_layout = QVBoxLayout(self._intro_card)
        intro_layout.setContentsMargins(
            layout_px(18),
            layout_px(16),
            layout_px(18),
            layout_px(16),
        )
        intro_layout.setSpacing(layout_px(8))

        summary_title_row = QHBoxLayout()
        summary_title_row.setContentsMargins(0, 0, 0, 0)
        summary_title_row.setSpacing(layout_px(8))
        summary_icon = filter_icon_label(
            "document",
            "candidateFiltersSummaryTitleIcon",
            layout_px(26),
            "#8FA2B7",
        )
        summary_title_row.addWidget(summary_icon)
        summary_title = QLabel(tr("candidates.filters.summary.title"))
        summary_title.setObjectName("candidateFiltersSummaryTitle")
        summary_title_row.addWidget(summary_title)
        summary_title_row.addStretch(1)
        intro_layout.addLayout(summary_title_row)

        self._intro_lead = QLabel(tr("candidates.filters.intro.lead"))
        self._intro_lead.setObjectName("candidateFiltersIntroLead")
        self._intro_lead.setWordWrap(True)
        intro_layout.addWidget(self._intro_lead)

        self._intro_stats = QLabel("")
        self._intro_stats.setObjectName("candidateFiltersIntroStats")
        self._intro_stats.setWordWrap(True)
        self._intro_stats.setVisible(False)
        intro_layout.addWidget(self._intro_stats)

        self._summary_value_labels: dict[str, QLabel] = {}

        def add_summary_row(key: str, icon_name: str, label_key: str) -> None:
            row = QFrame()
            row.setObjectName("candidateFiltersSummaryRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(layout_px(7))

            icon_label = filter_icon_label(
                icon_name,
                "candidateFiltersSummaryRowIcon",
                layout_px(18),
                "#8FA2B7",
            )
            row_layout.addWidget(icon_label)

            label = QLabel(tr(label_key))
            label.setObjectName("candidateFiltersSummaryRowLabel")
            row_layout.addWidget(label, stretch=1)

            value = QLabel("")
            value.setObjectName("candidateFiltersSummaryRowValue")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setWordWrap(True)
            row_layout.addWidget(value, stretch=1)
            self._summary_value_labels[key] = value

            intro_layout.addWidget(row)
            divider = QFrame()
            divider.setObjectName("candidateFiltersSummaryDivider")
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setFrameShadow(QFrame.Shadow.Plain)
            intro_layout.addWidget(divider)

        add_summary_row("countries", "globe", "candidates.filters.summary.countries")
        add_summary_row("media_type", "media", "candidates.filters.summary.media_type")
        add_summary_row("year", "calendar", "candidates.filters.summary.year")
        add_summary_row("preset", "heart", "candidates.filters.summary.preset")
        add_summary_row("vibe", "vibe", "candidates.filters.summary.vibe")
        add_summary_row("release", "clock", "candidates.filters.summary.release")
        add_summary_row("origin", "target", "candidates.filters.summary.origin")
        add_summary_row("replenish", "refresh", "candidates.filters.summary.replenish")

        intro_layout.addSpacing(layout_px(4))
        intro_layout.addWidget(self._apply_button)
        intro_layout.addWidget(self._reset_button)

        self._form = build_filters_form(
            year_max=self._year_max,
            on_year_range_changed=self._on_year_range_changed,
        )
        self._form.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(layout_px(16))
        content_layout.addWidget(self._form.scroll, stretch=1)
        content_layout.addWidget(self._intro_card, alignment=Qt.AlignmentFlag.AlignTop)
        root_layout.addLayout(content_layout, stretch=1)

        self._update_apply_button_width()
        self._update_year_range_label()
        self._refresh_threshold_labels()
        self._apply_filter_defaults()
        self._connect_summary_updates()
        session.add_listener(self._on_session_updated)
        session.add_loading_listener(self._on_loading_changed)
        self._update_intro()

    @property
    def widget(self) -> QWidget:
        return self._widget

    def reload_filter_options(self) -> None:
        """Reload pool-derived chip options while preserving the current selection."""
        selected_countries = self._country_selector.selected_country_codes()
        selected_include = self._include_genre_selector.selected_genres()
        selected_exclude = self._exclude_genre_selector.selected_genres()
        self._apply_filter_defaults(
            selected_countries=selected_countries,
            selected_include_genres=selected_include,
            selected_exclude_genres=selected_exclude,
            preserve_non_chip_filters=True,
        )

    @property
    def _country_selector(self):
        return self._form.country_selector

    @property
    def _year_range_label(self):
        return self._form.year_range_label

    @property
    def _media_type_combo(self):
        return self._form.media_type_combo

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

    @property
    def _replenish_enabled_check(self):
        return self._form.replenish_enabled_check

    @property
    def _replenish_preset_combo(self):
        return self._form.replenish_preset_combo

    @property
    def _replenish_animation_mode_combo(self):
        return self._form.replenish_animation_mode_combo

    @property
    def _replenish_vibe_combo(self):
        return self._form.replenish_vibe_combo

    @property
    def _replenish_release_preference_combo(self):
        return self._form.replenish_release_preference_combo

    @property
    def _replenish_origin_preference_combo(self):
        return self._form.replenish_origin_preference_combo

    @property
    def _replenish_advanced_override_check(self):
        return self._form.replenish_advanced_override_check

    def _connect_summary_updates(self) -> None:
        self._summary_update_callback = lambda *_args: self._update_summary_rows()
        update = self._summary_update_callback
        self._country_selector.selection_changed.connect(update)
        self._media_type_combo.currentIndexChanged.connect(update)
        self._year_slider.rangeChanged.connect(update)
        self._replenish_preset_combo.currentIndexChanged.connect(update)
        self._replenish_vibe_combo.currentIndexChanged.connect(update)
        self._replenish_release_preference_combo.currentIndexChanged.connect(update)
        self._replenish_origin_preference_combo.currentIndexChanged.connect(update)
        self._replenish_enabled_check.toggled.connect(update)

    def _summary_countries_text(self) -> str:
        country_codes = self._country_selector.selected_country_codes()
        if not country_codes:
            return tr("candidates.filters.summary.all")
        labels = [
            country_schema.build_country_display([code], language=self._interface_language) or code.upper()
            for code in country_codes[:3]
        ]
        countries = ", ".join(labels)
        if len(country_codes) <= 3:
            return countries
        return tr(
            "candidates.filters.summary.more",
            value=countries,
            count=len(country_codes) - 3,
        )

    def _summary_year_text(self) -> str:
        year_from, year_to = self._year_slider.values()
        return f"{year_from} \u2014 {year_to}"

    def _summary_replenish_text(self) -> str:
        if self._replenish_enabled_check.isChecked():
            return tr(
                "candidates.filters.summary.replenish_on",
                count=FILTER_REPLENISH_DEFAULT_BATCH_SIZE,
            )
        return tr("candidates.filters.summary.replenish_off")

    def _update_summary_rows(self) -> None:
        if not hasattr(self, "_summary_value_labels"):
            return
        values = {
            "countries": self._summary_countries_text(),
            "media_type": self._media_type_combo.currentText(),
            "year": self._summary_year_text(),
            "preset": self._replenish_preset_combo.currentText(),
            "vibe": self._replenish_vibe_combo.currentText(),
            "release": self._replenish_release_preference_combo.currentText(),
            "origin": self._replenish_origin_preference_combo.currentText(),
            "replenish": self._summary_replenish_text(),
        }
        for key, value in values.items():
            label = self._summary_value_labels.get(key)
            if label is not None:
                label.setText(str(value or tr("candidates.filters.summary.not_set")))

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
        self._intro_stats.setVisible(False)
        self._update_summary_rows()
        enabled = apply_enabled and self._session.is_loading is False and self._is_replenishing is False
        self._apply_button.setEnabled(enabled)
        self._reset_button.setEnabled(enabled)

    def _on_loading_changed(self) -> None:
        if self._session.is_loading:
            self._apply_button.setEnabled(False)
            self._reset_button.setEnabled(False)
            self._intro_lead.setText(tr("candidates.filters.loading.lead"))
            self._intro_stats.setText(tr("candidates.filters.loading.stats"))
            self._intro_stats.setVisible(True)
            return
        self._update_intro()

    def _on_session_updated(self) -> None:
        if self._session.is_loading:
            return
        local_apply_completed = self._local_apply_requested
        if self._session.last_error:
            self._pending_replenish_intent = None
            self._replenish_local_count_before = None
            self._local_apply_requested = False
            self._intro_lead.setText(tr("candidates.filters.error.lead"))
            self._intro_stats.setText(self._session.last_error)
            self._intro_stats.setVisible(True)
            self._apply_button.setEnabled(self._is_replenishing is False)
            self._reset_button.setEnabled(self._is_replenishing is False)
            return
        if self._session.has_results:
            self._update_intro(
                result_count=self._session.filtered_count,
                result_ok=self._session.filtered_count > 0,
            )
            if (
                local_apply_completed
                and self._pending_replenish_intent is None
                and self._is_replenishing is False
            ):
                self._intro_lead.setText("Local filter applied")
        if self._pending_replenish_intent is not None and self._replenish_worker is None:
            intent = self._pending_replenish_intent
            self._pending_replenish_intent = None
            self._replenish_local_count_before = int(self._session.filtered_count or 0)
            self._start_filter_replenish(
                intent,
                local_count_before=self._replenish_local_count_before,
            )
        self._local_apply_requested = False

    def _update_apply_button_width(self) -> None:
        if not hasattr(self, "_intro_card"):
            return
        content_width = self._intro_card.width() - layout_px(36)
        if content_width <= 0:
            content_width = SUMMARY_CARD_WIDTH - layout_px(36)
        target = max(control_px(148), content_width)
        self._apply_button.setFixedWidth(target)
        self._reset_button.setFixedWidth(target)
        self._apply_button.setFixedHeight(APPLY_BUTTON_HEIGHT)
        self._reset_button.setFixedHeight(APPLY_BUTTON_HEIGHT)

    def _on_year_range_changed(self, _lower: int, _upper: int) -> None:
        self._update_year_range_label()
        self._update_summary_rows()

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

    def _apply_filter_defaults(
        self,
        *,
        selected_countries: list[str] | None = None,
        selected_include_genres: list[str] | None = None,
        selected_exclude_genres: list[str] | None = None,
        preserve_non_chip_filters: bool = False,
    ) -> None:
        defaults_view = self._service.get_search_filter_defaults_view()
        defaults = defaults_view.get("defaults") or {}
        chip_view = self._service.get_search_filter_chip_options_view()
        raw_genre_labels = [
            str(item.get("label") or "").strip()
            for item in chip_view.get("genres") or []
            if str(item.get("label") or "").strip()
        ]
        genre_labels = _genre_labels_for_language(raw_genre_labels, self._data_language)
        include_selected = (
            selected_include_genres
            if selected_include_genres is not None
            else defaults.get("include_genres") or []
        )
        exclude_selected = (
            selected_exclude_genres
            if selected_exclude_genres is not None
            else defaults.get("exclude_genres") or []
        )
        self._genre_options = genre_labels
        self._include_genre_selector.set_options(
            genre_labels,
            _genre_labels_for_language(include_selected, self._data_language),
        )
        self._exclude_genre_selector.set_options(
            genre_labels,
            _genre_labels_for_language(exclude_selected, self._data_language),
        )

        country_options = [
            {
                "code": str(item.get("code") or "").strip(),
                "label": (
                    country_schema.build_country_display(
                        [str(item.get("code") or "").strip().upper()],
                        language=self._interface_language,
                    )
                    or str(item.get("label") or "").strip()
                ),
            }
            for item in chip_view.get("countries") or []
            if str(item.get("code") or "").strip()
        ]
        self._country_selector.set_options(
            country_options,
            selected_countries if selected_countries is not None else defaults.get("country"),
        )
        if preserve_non_chip_filters:
            return

        self._set_media_type_from_default(defaults.get("media_type"))
        self._set_year_slider_from_defaults(defaults.get("year_min"), defaults.get("year_max"))
        set_score_slider_from_default(self._tmdb_score_slider, defaults.get("min_tmdb_score"))
        set_votes_slider_from_default(self._tmdb_votes_slider, defaults.get("min_tmdb_votes"))
        self._refresh_threshold_labels()
        self._only_complete_check.setChecked(DEFAULT_BROWSE_FILTERS["only_complete"])
        self._only_unwatched_check.setChecked(DEFAULT_BROWSE_FILTERS["only_unwatched"])
        self._hide_hidden_check.setChecked(DEFAULT_BROWSE_FILTERS["hide_hidden"])

    def _set_media_type_from_default(self, media_type) -> None:
        index = self._media_type_combo.findData(media_type)
        self._media_type_combo.setCurrentIndex(index if index >= 0 else 0)

    def _collect_filters(self) -> dict:
        countries = self._country_selector.selected_country_codes()
        year_min, year_max = self._year_filter_bounds()

        return {
            "criteria_name": None,
            "source": None,
            "country": countries,
            "media_type": self._media_type_combo.currentData(),
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

    def _collect_replenish_intent(self, filters: dict) -> dict:
        return FilterReplenishIntent.from_filters(
            filters,
            preset_id=self._replenish_preset_combo.currentData(),
            animation_mode=self._replenish_animation_mode_combo.currentData(),
            vibe=self._replenish_vibe_combo.currentData(),
            release_preference=self._replenish_release_preference_combo.currentData(),
            origin_preference=self._replenish_origin_preference_combo.currentData(),
            target_add_count=clamp_filter_replenish_batch_size(FILTER_REPLENISH_DEFAULT_BATCH_SIZE),
            data_language=self._data_language,
            allow_advanced_override=self._replenish_advanced_override_check.isChecked(),
        ).to_dict()

    def _clear_filter_controls(self) -> None:
        self._country_selector.clear_selection()
        self._media_type_combo.setCurrentIndex(0)
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

    def on_before_apply(self, filters: dict) -> dict:
        """Extension seam for tests/future wrappers; default is no-op."""
        if self._on_before_apply is None:
            return filters
        return self._on_before_apply(filters)

    def _apply_filters(self) -> None:
        filters = self.on_before_apply(self._collect_filters())
        self._pending_replenish_intent = (
            self._collect_replenish_intent(filters)
            if self._replenish_enabled_check.isChecked()
            else None
        )
        self._replenish_local_count_before = None
        self._local_apply_requested = True
        self._session.apply_filters_async(filters, parent=self._widget)

        if self._on_applied is not None:
            self._on_applied()

    def _set_replenish_running(self, value: bool) -> None:
        self._is_replenishing = bool(value)
        self._apply_button.setEnabled(not self._is_replenishing and not self._session.is_loading)
        self._reset_button.setEnabled(not self._is_replenishing and not self._session.is_loading)

    def _start_filter_replenish(self, intent: dict, *, local_count_before: int | None = None) -> None:
        if self._replenish_worker is not None:
            return
        self._replenish_local_count_before = 0 if local_count_before is None else int(local_count_before)
        self._set_replenish_running(True)
        self._intro_lead.setText("Replenish started")
        self._intro_stats.setText("Local filter applied. Fetching matching TMDb candidates.")
        self._intro_stats.setVisible(True)
        worker = FilterReplenishWorker(intent, service=self._service, parent=self._widget)
        worker.progress.connect(self._on_replenish_progress)
        worker.finished_with_result.connect(self._on_replenish_finished)
        worker.failed.connect(self._on_replenish_failed)
        worker.finished.connect(lambda worker=worker: self._remove_replenish_worker(worker))
        worker.finished.connect(worker.deleteLater)
        self._replenish_worker = worker
        worker.start()

    def _on_replenish_progress(self, progress: object) -> None:
        if isinstance(progress, dict) is False:
            return
        bucket_id = progress.get("bucket_id") or "bucket"
        page = progress.get("page") or 1
        accepted = progress.get("accepted_count") or 0
        self._intro_stats.setText(f"Replenish {bucket_id}, page {page}, accepted {accepted}.")
        self._intro_stats.setVisible(True)

    def _on_replenish_finished(self, result: object) -> None:
        payload = dict(result or {}) if isinstance(result, dict) else {"ok": False, "error": "Invalid result"}
        self._last_replenish_result = payload
        self._set_replenish_running(False)
        if payload.get("blocked"):
            self._intro_lead.setText("Conflict: no TMDb call")
            self._intro_stats.setText("Selected replenish options have a compatibility conflict.")
            self._intro_stats.setVisible(True)
            return
        if payload.get("ok") is not True:
            self._intro_lead.setText("Replenish failed")
            self._intro_stats.setText(str(payload.get("error") or payload.get("message") or "Unknown error"))
            self._intro_stats.setVisible(True)
            return
        added = int(payload.get("saved_count") or payload.get("created_count") or 0)
        requested = int(payload.get("requested_count") or 30)
        local_before = 0 if self._replenish_local_count_before is None else int(self._replenish_local_count_before)
        self.reload_filter_options()
        reapplied = self._session.reload_from_pool(force=True)
        visible_after = int(reapplied.get("visible_count") or reapplied.get("filtered_count") or 0)
        self._intro_lead.setText("Replenish complete")
        self._intro_stats.setText(
            f"Before: {local_before}. Added {added} of {requested}. Visible now: {visible_after}."
            if added < requested
            else f"Before: {local_before}. Added {added}. Visible now: {visible_after}."
        )
        self._intro_stats.setVisible(True)

    def _on_replenish_failed(self, message: str) -> None:
        self._last_replenish_result = {"ok": False, "error": str(message)}
        self._set_replenish_running(False)
        self._intro_lead.setText("Replenish failed")
        self._intro_stats.setText(str(message or "Unknown error"))
        self._intro_stats.setVisible(True)

    def _remove_replenish_worker(self, worker: FilterReplenishWorker) -> None:
        if self._replenish_worker is worker:
            self._replenish_worker = None
