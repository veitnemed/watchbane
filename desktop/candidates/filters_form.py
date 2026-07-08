"""Scrollable filter form widgets for the candidate Filters tab."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

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
from desktop.theme.scaling import layout_px
from desktop.theme.shell_layout import CANDIDATE_ROOT_SPACING_PX

CANDIDATE_YEAR_MIN = 2000


@dataclass
class FiltersFormWidgets:
    """Widget handles for the filters scroll form."""

    scroll: QScrollArea
    country_selector: CountryChipSelector
    media_type_combo: QComboBox
    year_range_label: QLabel
    year_slider: RangeSlider
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
    form.setContentsMargins(0, 0, 0, 0)
    form.setSpacing(CANDIDATE_ROOT_SPACING_PX)

    def add_section(title: str) -> tuple[QFrame, QVBoxLayout]:
        section = QFrame()
        section.setObjectName("candidateFilterSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(
            layout_px(18),
            layout_px(16),
            layout_px(18),
            layout_px(18),
        )
        section_layout.setSpacing(layout_px(12))

        title_label = QLabel(title)
        title_label.setObjectName("candidateFilterSectionTitle")
        section_layout.addWidget(title_label)
        form.addWidget(section)
        return section, section_layout

    def add_divider(section_layout: QVBoxLayout) -> None:
        divider = QFrame()
        divider.setObjectName("candidateFilterDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        section_layout.addSpacing(layout_px(2))
        section_layout.addWidget(divider)
        section_layout.addSpacing(layout_px(2))

    _basic_section, basic_layout = add_section(tr("candidates.filters.basic"))
    country_selector = CountryChipSelector([])
    basic_layout.addWidget(field_label(tr("candidates.filters.country")))
    basic_layout.addWidget(country_selector)
    add_divider(basic_layout)

    media_type_combo = QComboBox()
    media_type_combo.setObjectName("candidateSearchMediaType")
    media_type_combo.addItem(tr("watched.filters.media_all"), None)
    media_type_combo.addItem(tr("media_type.tv"), "tv")
    media_type_combo.addItem(tr("media_type.movie"), "movie")
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
