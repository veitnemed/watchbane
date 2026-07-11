"""Desktop Filters tab for runtime candidate pool filtering."""

from __future__ import annotations

import json
from typing import Callable

from PyQt6.QtCore import QSize, QTimer, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from candidates import service as candidate_service
from candidates.preferences import (
    CandidateDiscoveryPreferences,
    RecommendationVector,
    SimpleRecommendationPreferences,
)
from candidates.models import country_schema, genre_schema
from candidates.onboarding.taste_presets import get_taste_preset
from candidates.recommendation_deck_service import (
    DEFAULT_ACTIVE_LIMIT,
    DEFAULT_REFILL_THRESHOLD,
    count_automatic_recommendation_candidates,
)
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
from desktop.settings.recommendation_preferences import (
    load_recommendation_preferences,
    load_simple_recommendation_preferences,
    save_discovery_preferences,
    save_recommendation_vector,
    save_simple_recommendation_preferences,
)
from desktop.theme.scaling import control_px, layout_px
from desktop.theme.shell_layout import (
    CANDIDATE_ROOT_MARGIN_PX,
    CANDIDATE_ROOT_SPACING_PX,
    LEFT_PANEL_TOP_COMPENSATION_PX,
)

APPLY_BUTTON_HEIGHT = control_px(40)
SUMMARY_CARD_WIDTH = layout_px(348)
FILTER_REPLENISH_DEFAULT_BATCH_SIZE = 30
FILTER_REPLENISH_MAX_BATCH_SIZE = 30


def clamp_filter_replenish_batch_size(value) -> int:
    """Return the safe per-apply replenish batch size."""
    try:
        requested = int(value)
    except (TypeError, ValueError):
        requested = FILTER_REPLENISH_DEFAULT_BATCH_SIZE
    return max(1, min(FILTER_REPLENISH_MAX_BATCH_SIZE, requested))


def _replenish_intent_signature(intent: dict) -> str:
    return json.dumps(dict(intent or {}), ensure_ascii=False, sort_keys=True, default=str)


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
        self._pending_replenish_generation: int | None = None
        self._replenish_local_count_before: int | None = None
        self._local_apply_requested = False
        self._replenish_generation = 0
        self._active_replenish_generation: int | None = None
        self._active_replenish_signature: str | None = None
        self._vector_debounce = QTimer()
        self._vector_debounce.setSingleShot(True)
        self._vector_debounce.setInterval(300)
        self._vector_debounce.timeout.connect(self._apply_vector_locally)

        view = self

        class CandidateFiltersRootWidget(QWidget):
            def resizeEvent(self, event) -> None:
                super().resizeEvent(event)
                view._update_summary_card_width()
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
            layout_px(16),
            layout_px(14),
            layout_px(16),
            layout_px(14),
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

        self._replenish_progress_bar = QProgressBar()
        self._replenish_progress_bar.setObjectName("candidateReplenishProgressBar")
        self._replenish_progress_bar.setRange(0, FILTER_REPLENISH_DEFAULT_BATCH_SIZE)
        self._replenish_progress_bar.setValue(0)
        self._replenish_progress_bar.setFormat(f"0 / {FILTER_REPLENISH_DEFAULT_BATCH_SIZE}")
        self._replenish_progress_bar.setTextVisible(True)
        self._replenish_progress_bar.setVisible(False)
        intro_layout.addWidget(self._replenish_progress_bar)

        self._summary_value_labels: dict[str, QLabel] = {}
        self._summary_name_labels: dict[str, QLabel] = {}
        self._summary_rows: dict[str, QFrame] = {}
        self._summary_dividers: dict[str, QFrame] = {}

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

            label = QLabel(tr(label_key))
            label.setObjectName("candidateFiltersSummaryRowLabel")

            value = QLabel("")
            value.setObjectName("candidateFiltersSummaryRowValue")
            value.setWordWrap(True)
            label.setWordWrap(True)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(icon_label)
            row_layout.addWidget(label, stretch=3)
            row_layout.addWidget(value, stretch=2)
            self._summary_value_labels[key] = value
            self._summary_name_labels[key] = label
            self._summary_rows[key] = row

            intro_layout.addWidget(row)
            divider = QFrame()
            divider.setObjectName("candidateFiltersSummaryDivider")
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setFrameShadow(QFrame.Shadow.Plain)
            self._summary_dividers[key] = divider
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
        self._set_simple_preferences_controls(load_simple_recommendation_preferences())
        self._discovery_preferences, self._recommendation_vector = load_recommendation_preferences()

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
        self._set_discovery_controls(self._discovery_preferences)
        self._set_vector_controls(self._recommendation_vector)
        self._session.recommendation_vector = self._recommendation_vector.to_dict()
        self._connect_summary_updates()
        self._connect_recommendation_controls()
        session.add_listener(self._on_session_updated)
        session.add_loading_listener(self._on_loading_changed)
        self._update_intro()

    @property
    def widget(self) -> QWidget:
        return self._widget

    def reload_filter_options(self) -> None:
        """Reload pool-derived chip options while preserving the current selection."""
        selected_countries = self._effective_country_codes()
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
    def _advanced_mode_toggle(self):
        return self._form.advanced_mode_toggle

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
        self._form.simple_media_combo.currentIndexChanged.connect(update)
        self._form.simple_collection_combo.currentIndexChanged.connect(update)
        self._form.simple_origin_combo.currentIndexChanged.connect(update)
        self._form.simple_mood_combo.currentIndexChanged.connect(update)
        self._advanced_mode_toggle.toggled.connect(update)

    def _connect_recommendation_controls(self) -> None:
        update = self._summary_update_callback
        self._form.direction_control.valueChanged.connect(self._on_direction_changed)
        for control in (
            self._form.discovery_media_control,
            self._form.discovery_animation_control,
            self._form.discovery_release_control,
        ):
            control.valueChanged.connect(update)
        for control in (
            self._form.vector_openness_control,
            self._form.vector_rarity_control,
            self._form.vector_diversity_control,
        ):
            control.sliderReleased.connect(self._schedule_vector_apply)
            control.valueChanged.connect(lambda _value: self._vector_debounce.start())
        self._form.vector_mood_control.valueChanged.connect(self._schedule_vector_apply)
        self._form.variation_button.clicked.connect(self._on_variation_requested)

    def _direction_values(self) -> list[str]:
        values = self._form.direction_control.property("directionValues")
        return [str(value) for value in values] if isinstance(values, list) else ["manual"]

    def _selected_direction_id(self) -> str:
        values = self._direction_values()
        index = max(0, min(len(values) - 1, self._form.direction_control.value()))
        return values[index]

    def _set_discovery_controls(self, preferences: CandidateDiscoveryPreferences) -> None:
        current = preferences.normalized()
        values = self._direction_values()
        self._form.direction_control.setValue(values.index(current.preset_id) if current.preset_id in values else 0)
        self._form.discovery_media_control.setValue(current.media_type)
        self._form.discovery_animation_control.setValue(current.animation_mode)
        self._form.discovery_release_control.setValue(current.release_preference)
        self._country_selector.set_selected_codes(list(current.countries))
        self._include_genre_selector.set_options(
            self._genre_options,
            _genre_labels_for_language(current.include_genres, self._data_language),
        )
        self._exclude_genre_selector.set_options(
            self._genre_options,
            _genre_labels_for_language(current.exclude_genres, self._data_language),
        )
        self._set_year_slider_from_defaults(current.year_min, current.year_max)
        set_score_slider_from_default(self._tmdb_score_slider, current.min_tmdb_score)
        set_votes_slider_from_default(self._tmdb_votes_slider, current.min_tmdb_votes)
        self._only_complete_check.setChecked(current.only_complete)
        self._only_unwatched_check.setChecked(current.only_unwatched)
        self._hide_hidden_check.setChecked(current.hide_hidden)

    def _set_vector_controls(self, vector: RecommendationVector) -> None:
        current = vector.normalized()
        self._form.vector_openness_control.setValue(current.openness_level)
        self._form.vector_rarity_control.setValue(current.rarity_level)
        self._form.vector_diversity_control.setValue(current.diversity_level)
        self._form.vector_mood_control.setValue(current.mood)

    def _collect_vector(self) -> RecommendationVector:
        return RecommendationVector(
            openness_level=self._form.vector_openness_control.value(),
            rarity_level=self._form.vector_rarity_control.value(),
            diversity_level=self._form.vector_diversity_control.value(),
            mood=self._form.vector_mood_control.value(),
        ).normalized()

    def _schedule_vector_apply(self, *_args) -> None:
        self._vector_debounce.start()

    def _apply_vector_locally(self) -> None:
        vector = self._collect_vector()
        self._recommendation_vector = vector
        save_recommendation_vector(vector)
        self._session.set_recommendation_vector(vector)

    def _on_variation_requested(self) -> None:
        self._session.next_recommendation_variation()

    def _on_direction_changed(self, _value: int) -> None:
        preset_id = self._selected_direction_id()
        if preset_id != "manual":
            preset = CandidateDiscoveryPreferences.from_preset(preset_id)
            self._form.discovery_media_control.setValue(preset.media_type)
            self._form.discovery_animation_control.setValue(preset.animation_mode)
            self._form.discovery_release_control.setValue(preset.release_preference)
            self._country_selector.set_selected_codes(list(preset.countries))
            self._include_genre_selector.set_options(
                self._genre_options,
                _genre_labels_for_language(preset.include_genres, self._data_language),
            )
        self._update_summary_rows()

    def _summary_countries_text(self) -> str:
        country_codes = self._effective_country_codes()
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
        if self._advanced_mode_toggle.isChecked() is False:
            media_labels = {
                "movie": tr("recommendations.discovery.media.movie"),
                "both": tr("recommendations.discovery.media.both"),
                "tv": tr("recommendations.discovery.media.tv"),
            }
            release_labels = {
                "classic": tr("recommendations.discovery.release.classic"),
                "mixed": tr("recommendations.discovery.release.mixed"),
                "new": tr("recommendations.discovery.release.new"),
            }
            simple_values = {
                "countries": ("candidates.filters.summary.countries", self._summary_countries_text()),
                "media_type": ("recommendations.discovery.media.label", media_labels[self._form.discovery_media_control.value()]),
                "year": ("recommendations.discovery.release.label", release_labels[self._form.discovery_release_control.value()]),
                "preset": ("recommendations.discovery.direction.label", self._form.direction_control.canonical_text()),
            }
            for key, row in self._summary_rows.items():
                visible = key in simple_values
                row.setVisible(visible)
                self._summary_dividers[key].setVisible(visible)
            for key, (label_key, value) in simple_values.items():
                self._summary_name_labels[key].setText(tr(label_key))
                self._summary_value_labels[key].setText(value)
            return
        advanced_label_keys = {
            "countries": "candidates.filters.summary.countries",
            "media_type": "candidates.filters.summary.media_type",
            "year": "candidates.filters.summary.year",
            "preset": "candidates.filters.summary.preset",
            "vibe": "candidates.filters.summary.vibe",
            "release": "candidates.filters.summary.release",
            "origin": "candidates.filters.summary.origin",
            "replenish": "candidates.filters.summary.replenish",
        }
        for key, row in self._summary_rows.items():
            row.show()
            self._summary_dividers[key].show()
            self._summary_name_labels[key].setText(tr(advanced_label_keys[key]))
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

    def _set_simple_preferences_controls(self, preferences: SimpleRecommendationPreferences) -> None:
        values = preferences.normalized().to_dict()
        for combo, key in (
            (self._form.simple_media_combo, "media"),
            (self._form.simple_collection_combo, "collection"),
            (self._form.simple_origin_combo, "origin"),
            (self._form.simple_mood_combo, "mood"),
        ):
            index = combo.findData(values[key])
            combo.setCurrentIndex(index if index >= 0 else 0)

    def _simple_preferences_from_controls(self) -> SimpleRecommendationPreferences:
        return SimpleRecommendationPreferences(
            media=str(self._form.simple_media_combo.currentData() or "both"),
            collection=str(self._form.simple_collection_combo.currentData() or "mixed"),
            origin=str(self._form.simple_origin_combo.currentData() or "any"),
            mood=str(self._form.simple_mood_combo.currentData() or "any"),
        ).normalized()

    def _simple_pool_needs_replenish(
        self,
        preferences: SimpleRecommendationPreferences,
    ) -> bool:
        filters = preferences.to_candidate_filters(DEFAULT_BROWSE_FILTERS)
        filters["only_unwatched"] = True
        filters["hide_hidden"] = True
        candidates = list(self._session.overview().get("candidates") or [])
        try:
            search_view = self._service.search_candidate_pool(candidates, filters)
            matching = list(
                search_view.get("filtered_candidates")
                or search_view.get("candidates")
                or []
            )
        except Exception:
            matching = candidates
        eligible_count = count_automatic_recommendation_candidates(
            matching,
            filters,
            capacity=DEFAULT_ACTIVE_LIMIT + DEFAULT_REFILL_THRESHOLD,
        )
        return eligible_count < DEFAULT_ACTIVE_LIMIT + DEFAULT_REFILL_THRESHOLD

    def _discovery_pool_needs_replenish(
        self,
        preferences: CandidateDiscoveryPreferences,
    ) -> bool:
        filters = preferences.to_candidate_filters(DEFAULT_BROWSE_FILTERS)
        filters["only_unwatched"] = True
        filters["hide_hidden"] = True
        candidates = list(self._session.overview().get("candidates") or [])
        try:
            search_view = self._service.search_candidate_pool(candidates, filters)
            matching = list(
                search_view.get("filtered_candidates")
                or search_view.get("candidates")
                or []
            )
        except Exception:
            matching = candidates
        eligible_count = count_automatic_recommendation_candidates(
            matching,
            self._collect_vector(),
            capacity=DEFAULT_ACTIVE_LIMIT + DEFAULT_REFILL_THRESHOLD,
        )
        return eligible_count < DEFAULT_ACTIVE_LIMIT + DEFAULT_REFILL_THRESHOLD

    def _selected_replenish_preset(self):
        preset_id = self._replenish_preset_combo.currentData()
        if preset_id in (None, "", "manual"):
            return None
        return get_taste_preset(str(preset_id or ""))

    def _effective_country_codes(self) -> list[str]:
        selected = self._country_selector.selected_country_codes()
        if selected:
            return selected
        preset = get_taste_preset(self._selected_direction_id())
        if preset is None:
            return []
        return [
            str(code).strip().upper()
            for code in preset.countries
            if str(code).strip()
        ]

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
            self._pending_replenish_generation = None
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
                self._intro_lead.setText(tr("recommendations.discovery.status.local_applied"))
        if self._pending_replenish_intent is not None and self._replenish_worker is None:
            intent = self._pending_replenish_intent
            generation = self._pending_replenish_generation
            self._pending_replenish_intent = None
            self._pending_replenish_generation = None
            self._replenish_local_count_before = int(self._session.filtered_count or 0)
            self._start_filter_replenish(
                intent,
                local_count_before=self._replenish_local_count_before,
                generation=generation,
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

    def _update_summary_card_width(self) -> None:
        if not hasattr(self, "_intro_card"):
            return
        available_width = max(
            0,
            self._widget.width() - (2 * CANDIDATE_ROOT_MARGIN_PX) - layout_px(16),
        )
        proportional_width = int(available_width * 0.32)
        target_width = min(
            SUMMARY_CARD_WIDTH,
            max(layout_px(240), proportional_width),
        )
        self._intro_card.setFixedWidth(target_width)

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
        countries = self._effective_country_codes()
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
        self._set_discovery_controls(CandidateDiscoveryPreferences())
        self._set_vector_controls(RecommendationVector())
        self._apply_vector_locally()
        self._apply_filters()

    def on_before_apply(self, filters: dict) -> dict:
        """Extension seam for tests/future wrappers; default is no-op."""
        if self._on_before_apply is None:
            return filters
        return self._on_before_apply(filters)

    def _apply_filters(self) -> None:
        self._replenish_generation += 1
        if self._replenish_worker is not None:
            self._replenish_worker.cancel()
        preferences = self._collect_discovery_preferences()
        self._discovery_preferences = preferences
        save_discovery_preferences(preferences)
        filters = self.on_before_apply(
            preferences.to_candidate_filters(DEFAULT_BROWSE_FILTERS)
        )
        self._pending_replenish_intent = (
            preferences.to_replenish_intent(
                data_language=self._data_language,
                target_add_count=FILTER_REPLENISH_DEFAULT_BATCH_SIZE,
            )
            if self._discovery_pool_needs_replenish(preferences)
            else None
        )
        self._pending_replenish_generation = (
            self._replenish_generation
            if self._pending_replenish_intent is not None
            else None
        )
        if self._pending_replenish_intent is None:
            self._hide_replenish_progress()
        self._replenish_local_count_before = None
        self._local_apply_requested = True
        self._session.apply_filters_async(filters, parent=self._widget)

        if self._on_applied is not None:
            self._on_applied()

    def _set_replenish_running(self, value: bool) -> None:
        self._is_replenishing = bool(value)
        self._apply_button.setEnabled(not self._is_replenishing and not self._session.is_loading)
        self._reset_button.setEnabled(not self._is_replenishing and not self._session.is_loading)

    def _set_replenish_progress(self, value: int, maximum: int) -> None:
        maximum = max(1, int(maximum or FILTER_REPLENISH_DEFAULT_BATCH_SIZE))
        value = max(0, min(maximum, int(value or 0)))
        self._replenish_progress_bar.setRange(0, maximum)
        self._replenish_progress_bar.setValue(value)
        self._replenish_progress_bar.setFormat(f"{value} / {maximum}")
        self._replenish_progress_bar.setVisible(True)

    def _hide_replenish_progress(self) -> None:
        self._replenish_progress_bar.setRange(0, FILTER_REPLENISH_DEFAULT_BATCH_SIZE)
        self._replenish_progress_bar.setValue(0)
        self._replenish_progress_bar.setFormat(f"0 / {FILTER_REPLENISH_DEFAULT_BATCH_SIZE}")
        self._replenish_progress_bar.setVisible(False)

    def request_recommendation_refill(self, preferences: dict) -> bool:
        """Queue one async refill for the currently active recommendation intent."""
        discovery = getattr(self, "_discovery_preferences", CandidateDiscoveryPreferences())
        intent = FilterReplenishIntent.from_filters(
            dict(preferences or {}),
            preset_id=discovery.preset_id,
            animation_mode=discovery.animation_mode,
            release_preference=discovery.release_preference,
            target_add_count=FILTER_REPLENISH_DEFAULT_BATCH_SIZE,
            data_language=self._data_language,
        ).to_dict()
        signature = _replenish_intent_signature(intent)
        if self._replenish_worker is not None:
            if signature == self._active_replenish_signature:
                return False
            self._replenish_generation += 1
            self._replenish_worker.cancel()
            self._pending_replenish_intent = intent
            self._pending_replenish_generation = self._replenish_generation
            return True
        return self._start_filter_replenish(intent, generation=self._replenish_generation)

    def _collect_discovery_preferences(self) -> CandidateDiscoveryPreferences:
        year_min, year_max = self._year_filter_bounds()
        return CandidateDiscoveryPreferences(
            preset_id=self._selected_direction_id(),
            media_type=self._form.discovery_media_control.value(),
            animation_mode=self._form.discovery_animation_control.value(),
            release_preference=self._form.discovery_release_control.value(),
            countries=tuple(self._effective_country_codes()),
            include_genres=tuple(self._include_genre_selector.selected_genres()),
            exclude_genres=tuple(self._exclude_genre_selector.selected_genres()),
            year_min=year_min,
            year_max=year_max,
            min_tmdb_score=min_score_from_slider(self._tmdb_score_slider),
            min_tmdb_votes=min_votes_from_slider(self._tmdb_votes_slider),
            only_complete=self._only_complete_check.isChecked(),
            only_unwatched=self._only_unwatched_check.isChecked(),
            hide_hidden=self._hide_hidden_check.isChecked(),
        ).normalized()

    def _start_filter_replenish(
        self,
        intent: dict,
        *,
        local_count_before: int | None = None,
        generation: int | None = None,
    ) -> bool:
        signature = _replenish_intent_signature(intent)
        if self._replenish_worker is not None:
            return False
        request_generation = self._replenish_generation if generation is None else int(generation)
        self._replenish_local_count_before = 0 if local_count_before is None else int(local_count_before)
        self._set_replenish_running(True)
        target = clamp_filter_replenish_batch_size(intent.get("target_add_count", FILTER_REPLENISH_DEFAULT_BATCH_SIZE))
        self._set_replenish_progress(0, target)
        self._intro_lead.setText(tr("candidates.filters.replenish.status.started"))
        self._intro_stats.setText(tr("candidates.filters.replenish.status.fetching"))
        self._intro_stats.setVisible(True)
        worker = FilterReplenishWorker(intent, service=self._service, parent=self._widget)
        worker.progress.connect(
            lambda progress, request_generation=request_generation: self._on_replenish_progress(
                progress,
                request_generation,
            )
        )
        worker.finished_with_result.connect(
            lambda result, request_generation=request_generation: self._on_replenish_finished(
                result,
                request_generation,
            )
        )
        worker.failed.connect(
            lambda message, request_generation=request_generation: self._on_replenish_failed(
                message,
                request_generation,
            )
        )
        worker.finished.connect(lambda worker=worker: self._remove_replenish_worker(worker))
        worker.finished.connect(worker.deleteLater)
        self._replenish_worker = worker
        self._active_replenish_generation = request_generation
        self._active_replenish_signature = signature
        worker.start()
        return True

    def _on_replenish_progress(self, progress: object, generation: int | None = None) -> None:
        if generation is not None and generation != self._replenish_generation:
            return
        if isinstance(progress, dict) is False:
            return
        accepted = int(progress.get("accepted_count") or 0)
        selected = int(progress.get("selected_count") or accepted)
        target = int(progress.get("target_count") or self._replenish_progress_bar.maximum() or FILTER_REPLENISH_DEFAULT_BATCH_SIZE)
        self._set_replenish_progress(selected, target)
        self._intro_stats.setText(
            tr("candidates.filters.replenish.status.progress", current=selected, total=target)
        )
        self._intro_stats.setVisible(True)

    def _on_replenish_finished(self, result: object, generation: int | None = None) -> None:
        if generation is not None and generation != self._replenish_generation:
            self._set_replenish_running(False)
            return
        payload = dict(result or {}) if isinstance(result, dict) else {"ok": False, "error": "Invalid result"}
        self._last_replenish_result = payload
        self._set_replenish_running(False)
        if payload.get("blocked"):
            self._hide_replenish_progress()
            self._intro_lead.setText(tr("recommendations.discovery.status.conflict"))
            self._intro_stats.setText(tr("recommendations.discovery.status.conflict_detail"))
            self._intro_stats.setVisible(True)
            return
        if payload.get("ok") is not True:
            self._hide_replenish_progress()
            self._intro_lead.setText(tr("recommendations.discovery.status.failed"))
            self._intro_stats.setText(str(payload.get("error") or payload.get("message") or tr("common.unknown_error")))
            self._intro_stats.setVisible(True)
            return
        added = int(payload.get("saved_count") or payload.get("created_count") or 0)
        requested = int(payload.get("requested_count") or 30)
        self._set_replenish_progress(added, requested)
        local_before = 0 if self._replenish_local_count_before is None else int(self._replenish_local_count_before)
        self.reload_filter_options()
        reapplied = self._session.reload_from_pool(force=True)
        visible_after = int(reapplied.get("visible_count") or reapplied.get("filtered_count") or 0)
        self._intro_lead.setText(tr("recommendations.discovery.status.complete"))
        self._intro_stats.setText(
            tr("recommendations.discovery.status.complete_partial", before=local_before, added=added, requested=requested, visible=visible_after)
            if added < requested
            else tr("recommendations.discovery.status.complete_full", before=local_before, added=added, visible=visible_after)
        )
        self._intro_stats.setVisible(True)

    def _on_replenish_failed(self, message: str, generation: int | None = None) -> None:
        if generation is not None and generation != self._replenish_generation:
            self._set_replenish_running(False)
            return
        self._last_replenish_result = {"ok": False, "error": str(message)}
        self._set_replenish_running(False)
        self._hide_replenish_progress()
        self._intro_lead.setText(tr("recommendations.discovery.status.failed"))
        self._intro_stats.setText(str(message or tr("common.unknown_error")))
        self._intro_stats.setVisible(True)

    def _remove_replenish_worker(self, worker: FilterReplenishWorker) -> None:
        if self._replenish_worker is worker:
            self._replenish_worker = None
            self._active_replenish_generation = None
            self._active_replenish_signature = None
            if self._pending_replenish_intent is not None and self._session.is_loading is False:
                intent = self._pending_replenish_intent
                generation = self._pending_replenish_generation
                self._pending_replenish_intent = None
                self._pending_replenish_generation = None
                self._start_filter_replenish(intent, generation=generation)
