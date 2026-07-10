"""Scrollable filter form widgets for the candidate Filters tab."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from candidates.onboarding.taste_presets import get_taste_preset
from desktop.candidates.filter_icon_assets import filter_icon_label
from desktop.candidates.filters_controls import (
    SCORE_SLIDER_MAX,
    VOTES_SLIDER_MAX_INDEX,
    add_threshold_filter_row,
    field_label,
    make_min_threshold_slider,
    update_score_range_label,
    update_votes_range_label,
)
from desktop.candidates.session import DEFAULT_BROWSE_FILTERS
from desktop.i18n import tr
from desktop.shared.widgets.country_chip_selector import CountryChipSelector
from desktop.shared.widgets.genre_chip_selector import GenreChipSelector
from desktop.shared.widgets.range_slider import RangeSlider
from desktop.theme import TRANSPARENT_STYLE
from desktop.theme.scaling import get_ui_scale, layout_px

CANDIDATE_YEAR_MIN = 2000

REPLENISH_PRESETS = (
    ("candidates.filters.replenish.preset.manual", "manual"),
    ("candidates.filters.replenish.preset.hollywood_mainstream", "hollywood_mainstream"),
    ("candidates.filters.replenish.preset.russian_mainstream", "russian_mainstream"),
    ("candidates.filters.replenish.preset.anime", "anime"),
    ("candidates.filters.replenish.preset.k_drama", "k_drama"),
    ("candidates.filters.replenish.preset.turkish_dramas", "turkish_dramas"),
    ("candidates.filters.replenish.preset.british_european_detective", "british_european_detective"),
    ("candidates.filters.replenish.preset.family_animation", "family_animation"),
    ("candidates.filters.replenish.preset.dark_thriller_crime", "dark_thriller_crime"),
)
ANIMATION_MODE_OPTIONS = (
    ("candidates.filters.replenish.animation.any", "any"),
    ("candidates.filters.replenish.animation.animation_only", "animation_only"),
    ("candidates.filters.replenish.animation.live_action_only", "live_action_only"),
)
VIBE_OPTIONS = (
    ("candidates.filters.replenish.vibe.mixed", "mixed"),
    ("candidates.filters.replenish.vibe.light", "light"),
    ("candidates.filters.replenish.vibe.dark", "dark"),
)
RELEASE_OPTIONS = (
    ("candidates.filters.replenish.release.mixed", "mixed"),
    ("candidates.filters.replenish.release.new", "new"),
    ("candidates.filters.replenish.release.classic", "classic"),
)
ORIGIN_OPTIONS = (
    ("candidates.filters.replenish.origin.any", "any"),
    ("candidates.filters.replenish.origin.domestic", "domestic"),
    ("candidates.filters.replenish.origin.foreign", "foreign"),
    ("candidates.filters.replenish.origin.mixed", "mixed"),
)


@dataclass
class FiltersFormWidgets:
    """Widget handles for the filters scroll form."""

    scroll: QScrollArea
    country_selector: CountryChipSelector
    media_type_combo: QComboBox
    year_range_label: QLabel
    year_slider: RangeSlider
    replenish_preset_combo: QComboBox
    replenish_animation_mode_combo: QComboBox
    replenish_vibe_combo: QComboBox
    replenish_release_preference_combo: QComboBox
    replenish_origin_preference_combo: QComboBox
    replenish_enabled_check: QCheckBox
    replenish_advanced_override_check: QCheckBox
    include_genre_selector: GenreChipSelector
    exclude_genre_selector: GenreChipSelector
    tmdb_score_range_label: QLabel
    tmdb_score_slider: RangeSlider
    tmdb_votes_range_label: QLabel
    tmdb_votes_slider: RangeSlider
    only_complete_check: QCheckBox
    only_unwatched_check: QCheckBox
    hide_hidden_check: QCheckBox


def build_filters_form(
    *,
    year_max: int,
    on_year_range_changed: Callable[[int, int], None],
) -> FiltersFormWidgets:
    """Build the scrollable filter form and return widget handles."""
    scroll = QScrollArea()
    scroll.setObjectName("candidateSearchFiltersScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    form_host = QWidget()
    form_host.setObjectName("candidateSearchFiltersHost")
    form = QVBoxLayout(form_host)
    form.setContentsMargins(0, 0, layout_px(10), 0)
    form.setSpacing(layout_px(12))
    compact_combo_max_width = layout_px(420)
    section_index = 0
    section_icons = ("filter", "heart", "refresh", "target", "document")

    def add_section(title: str) -> tuple[QFrame, QVBoxLayout]:
        nonlocal section_index
        section_index += 1
        section = QFrame()
        section.setObjectName("candidateFilterSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(
            layout_px(14),
            layout_px(12),
            layout_px(14),
            layout_px(14),
        )
        section_layout.setSpacing(layout_px(10))

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(layout_px(8))
        badge = filter_icon_label(
            section_icons[min(section_index - 1, len(section_icons) - 1)],
            "candidateFilterSectionBadge",
            layout_px(24),
            "#22D3C5",
        )
        title_label = QLabel(f"{section_index}. {title}")
        title_label.setObjectName("candidateFilterSectionTitle")
        title_row.addWidget(badge)
        title_row.addWidget(title_label)
        title_row.addStretch(1)
        section_layout.addLayout(title_row)
        form.addWidget(section)
        return section, section_layout

    def add_divider(section_layout: QVBoxLayout) -> None:
        divider = QFrame()
        divider.setObjectName("candidateFilterDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        section_layout.addSpacing(layout_px(1))
        section_layout.addWidget(divider)
        section_layout.addSpacing(layout_px(1))

    def make_hint(text: str) -> QLabel:
        hint = QLabel(text)
        hint.setObjectName("candidateSearchHint")
        hint.setWordWrap(True)
        return hint

    def add_hint(section_layout: QVBoxLayout, text: str) -> QLabel:
        hint = make_hint(text)
        section_layout.addWidget(hint)
        return hint

    def constrain_combo_width(combo: QComboBox) -> None:
        combo.setMaximumWidth(compact_combo_max_width)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    _basic_section, basic_layout = add_section(tr("candidates.filters.basic"))
    country_selector = CountryChipSelector([])
    basic_layout.addWidget(field_label(tr("candidates.filters.country")))
    basic_layout.addWidget(country_selector)
    add_hint(basic_layout, tr("candidates.filters.country_hint"))
    add_divider(basic_layout)

    media_type_combo = QComboBox()
    media_type_combo.setObjectName("candidateSearchMediaType")
    media_type_combo.addItem(tr("watched.filters.media_all"), None)
    media_type_combo.addItem(tr("media_type.tv"), "tv")
    media_type_combo.addItem(tr("media_type.movie"), "movie")
    constrain_combo_width(media_type_combo)
    basic_layout.addWidget(field_label(tr("candidates.filters.media_type")))
    basic_layout.addWidget(media_type_combo)
    add_divider(basic_layout)

    year_header = QHBoxLayout()
    year_header.setContentsMargins(0, 0, 0, 0)
    year_header.setSpacing(layout_px(8))
    year_header.addWidget(field_label(tr("candidates.filters.year")))
    year_header.addStretch()
    year_range_label = QLabel("")
    year_range_label.setObjectName("candidateSearchYearRangeLabel")
    year_header.addWidget(year_range_label)
    basic_layout.addLayout(year_header)

    year_slider = RangeSlider(
        CANDIDATE_YEAR_MIN,
        year_max,
        CANDIDATE_YEAR_MIN,
        year_max,
    )
    year_slider.setObjectName("candidateSearchYearRange")
    year_slider.rangeChanged.connect(on_year_range_changed)
    basic_layout.addWidget(year_slider)

    def add_combo(options: tuple[tuple[str, str], ...], object_name: str) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(object_name)
        for label_key, value in options:
            combo.addItem(tr(label_key), value)
        constrain_combo_width(combo)
        return combo

    def set_combo_data(combo: QComboBox, value: str | None) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    _replenish_section, replenish_layout = add_section(tr("candidates.filters.replenish.title"))
    replenish_preset_combo = add_combo(REPLENISH_PRESETS, "candidateReplenishPreset")
    replenish_animation_mode_combo = add_combo(ANIMATION_MODE_OPTIONS, "candidateReplenishAnimationMode")
    replenish_vibe_combo = add_combo(VIBE_OPTIONS, "candidateReplenishVibe")
    replenish_release_preference_combo = add_combo(RELEASE_OPTIONS, "candidateReplenishReleasePreference")
    replenish_origin_preference_combo = add_combo(ORIGIN_OPTIONS, "candidateReplenishOriginPreference")
    replenish_enabled_check = QCheckBox(tr("candidates.filters.replenish.enable"))
    replenish_enabled_check.setObjectName("candidateReplenishEnabled")
    replenish_enabled_check.setChecked(False)
    replenish_advanced_override_check = QCheckBox(tr("candidates.filters.replenish.advanced_override"))
    replenish_advanced_override_check.setObjectName("candidateReplenishAdvancedOverride")
    replenish_advanced_override_check.setChecked(False)

    replenish_action_row = QWidget()
    replenish_action_row.setObjectName("candidateReplenishActionRow")
    replenish_action_row.setStyleSheet(TRANSPARENT_STYLE)
    action_layout_cls = QVBoxLayout if get_ui_scale() >= 1.25 else QHBoxLayout
    replenish_action_layout = action_layout_cls(replenish_action_row)
    replenish_action_layout.setContentsMargins(0, 0, 0, 0)
    replenish_action_layout.setSpacing(layout_px(10))
    replenish_action_layout.addWidget(replenish_enabled_check)
    replenish_action_layout.addWidget(replenish_advanced_override_check)
    if isinstance(replenish_action_layout, QHBoxLayout):
        replenish_action_layout.addStretch(1)
    replenish_layout.addWidget(replenish_action_row)
    replenish_layout.addWidget(make_hint(tr("candidates.filters.replenish.hint.advanced_override")))
    add_divider(replenish_layout)

    replenish_grid = QGridLayout()
    replenish_grid.setContentsMargins(0, 0, 0, 0)
    replenish_grid.setHorizontalSpacing(layout_px(16))
    replenish_grid.setVerticalSpacing(layout_px(12))
    replenish_column_count = 1 if get_ui_scale() >= 1.25 else 2
    for column in range(replenish_column_count):
        replenish_grid.setColumnStretch(column, 1)

    def replenish_grid_position(index: int) -> tuple[int, int]:
        return index // replenish_column_count, index % replenish_column_count

    def add_replenish_field(
        row: int,
        column: int,
        label_text: str,
        combo: QComboBox,
        *,
        hint_text: str | None = None,
    ) -> None:
        cell = QWidget()
        cell.setObjectName("candidateReplenishField")
        cell.setStyleSheet(TRANSPARENT_STYLE)
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(layout_px(6))
        cell_layout.addWidget(field_label(label_text))
        cell_layout.addWidget(combo)
        if hint_text:
            cell_layout.addWidget(make_hint(hint_text))
        replenish_grid.addWidget(cell, row, column)

    row, column = replenish_grid_position(0)
    add_replenish_field(
        row,
        column,
        tr("candidates.filters.replenish.preset"),
        replenish_preset_combo,
        hint_text=tr("candidates.filters.replenish.hint.anime"),
    )
    row, column = replenish_grid_position(1)
    add_replenish_field(
        row,
        column,
        tr("candidates.filters.replenish.animation_mode"),
        replenish_animation_mode_combo,
        hint_text=tr("candidates.filters.replenish.hint.live_action"),
    )
    row, column = replenish_grid_position(2)
    add_replenish_field(row, column, tr("candidates.filters.replenish.vibe"), replenish_vibe_combo)
    row, column = replenish_grid_position(3)
    add_replenish_field(
        row,
        column,
        tr("candidates.filters.replenish.release_preference"),
        replenish_release_preference_combo,
    )
    row, column = replenish_grid_position(4)
    add_replenish_field(
        row,
        column,
        tr("candidates.filters.replenish.origin_preference"),
        replenish_origin_preference_combo,
    )
    replenish_layout.addLayout(replenish_grid)

    def apply_preset_suggestion() -> None:
        preset_id = replenish_preset_combo.currentData()
        if preset_id == "manual":
            return
        preset = get_taste_preset(str(preset_id or ""))
        if preset is None:
            return
        country_selector.set_selected_codes(list(preset.countries))
        set_combo_data(media_type_combo, None if preset.media_type == "both" else preset.media_type)
        set_combo_data(replenish_animation_mode_combo, preset.animation_mode)
        set_combo_data(replenish_vibe_combo, preset.vibe)
        set_combo_data(replenish_release_preference_combo, preset.release_preference)

    replenish_preset_combo.currentIndexChanged.connect(apply_preset_suggestion)

    _genres_section, genres_layout = add_section(tr("candidates.filters.genres"))
    include_genre_selector = GenreChipSelector(object_name="candidateSearchIncludeGenres")
    exclude_genre_selector = GenreChipSelector(object_name="candidateSearchExcludeGenres")
    genres_layout.addWidget(field_label(tr("candidates.filters.include")))
    genres_layout.addWidget(include_genre_selector)
    add_divider(genres_layout)
    genres_layout.addWidget(field_label(tr("candidates.filters.exclude")))
    genres_layout.addWidget(exclude_genre_selector)

    _tmdb_section, tmdb_layout = add_section(tr("candidates.filters.tmdb"))
    tmdb_score_range_label = QLabel("")
    tmdb_score_range_label.setObjectName("candidateSearchFilterValue")
    tmdb_score_slider = make_min_threshold_slider(
        0,
        SCORE_SLIDER_MAX,
        "candidateSearchTmdbScoreRange",
        lambda: update_score_range_label(tmdb_score_slider, tmdb_score_range_label),
    )
    add_threshold_filter_row(tmdb_layout, tr("candidates.filters.score"), tmdb_score_range_label, tmdb_score_slider)
    add_divider(tmdb_layout)

    tmdb_votes_range_label = QLabel("")
    tmdb_votes_range_label.setObjectName("candidateSearchFilterValue")
    tmdb_votes_slider = make_min_threshold_slider(
        0,
        VOTES_SLIDER_MAX_INDEX,
        "candidateSearchTmdbVotesRange",
        lambda: update_votes_range_label(tmdb_votes_slider, tmdb_votes_range_label),
    )
    add_threshold_filter_row(tmdb_layout, tr("candidates.filters.votes"), tmdb_votes_range_label, tmdb_votes_slider)

    _visibility_section, visibility_layout = add_section(tr("candidates.filters.visibility"))
    only_complete_check = QCheckBox(tr("candidates.filters.only_complete"))
    only_complete_check.setObjectName("candidateSearchOnlyComplete")
    only_complete_check.setChecked(DEFAULT_BROWSE_FILTERS["only_complete"])
    only_unwatched_check = QCheckBox(tr("candidates.filters.only_unwatched"))
    only_unwatched_check.setObjectName("candidateSearchOnlyUnwatched")
    only_unwatched_check.setChecked(DEFAULT_BROWSE_FILTERS["only_unwatched"])
    hide_hidden_check = QCheckBox(tr("candidates.filters.hide_hidden"))
    hide_hidden_check.setObjectName("candidateSearchHideHidden")
    hide_hidden_check.setChecked(DEFAULT_BROWSE_FILTERS["hide_hidden"])
    visibility_layout.addWidget(only_complete_check)
    visibility_layout.addWidget(only_unwatched_check)
    visibility_layout.addWidget(hide_hidden_check)
    form.addStretch(1)

    scroll.setWidget(form_host)

    return FiltersFormWidgets(
        scroll=scroll,
        country_selector=country_selector,
        media_type_combo=media_type_combo,
        year_range_label=year_range_label,
        year_slider=year_slider,
        replenish_preset_combo=replenish_preset_combo,
        replenish_animation_mode_combo=replenish_animation_mode_combo,
        replenish_vibe_combo=replenish_vibe_combo,
        replenish_release_preference_combo=replenish_release_preference_combo,
        replenish_origin_preference_combo=replenish_origin_preference_combo,
        replenish_enabled_check=replenish_enabled_check,
        replenish_advanced_override_check=replenish_advanced_override_check,
        include_genre_selector=include_genre_selector,
        exclude_genre_selector=exclude_genre_selector,
        tmdb_score_range_label=tmdb_score_range_label,
        tmdb_score_slider=tmdb_score_slider,
        tmdb_votes_range_label=tmdb_votes_range_label,
        tmdb_votes_slider=tmdb_votes_slider,
        only_complete_check=only_complete_check,
        only_unwatched_check=only_unwatched_check,
        hide_hidden_check=hide_hidden_check,
    )
