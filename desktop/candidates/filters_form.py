"""Scrollable filter form widgets for the candidate Filters tab."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

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
from desktop.shared.widgets.country_chip_selector import CountryChipSelector
from desktop.shared.widgets.genre_chip_selector import GenreChipSelector
from desktop.shared.widgets.range_slider import RangeSlider

CANDIDATE_YEAR_MIN = 2000


@dataclass
class FiltersFormWidgets:
    """Widget handles for the filters scroll form."""

    scroll: QScrollArea
    country_selector: CountryChipSelector
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
    form.setSpacing(12)

    country_selector = CountryChipSelector([])
    form.addWidget(field_label("Страна"))
    form.addWidget(country_selector)

    year_header = QHBoxLayout()
    year_header.setContentsMargins(0, 0, 0, 0)
    year_header.addWidget(field_label("Год"))
    year_header.addStretch()
    year_range_label = QLabel("")
    year_range_label.setObjectName("candidateSearchYearRangeLabel")
    year_header.addWidget(year_range_label)
    form.addLayout(year_header)

    year_slider = RangeSlider(
        CANDIDATE_YEAR_MIN,
        year_max,
        CANDIDATE_YEAR_MIN,
        year_max,
    )
    year_slider.setObjectName("candidateSearchYearRange")
    year_slider.rangeChanged.connect(on_year_range_changed)
    form.addWidget(year_slider)

    include_genre_selector = GenreChipSelector(object_name="candidateSearchIncludeGenres")
    exclude_genre_selector = GenreChipSelector(object_name="candidateSearchExcludeGenres")
    form.addWidget(field_label("Включить жанры"))
    form.addWidget(include_genre_selector)
    form.addWidget(field_label("Исключить жанры"))
    form.addWidget(exclude_genre_selector)

    tmdb_score_range_label = QLabel("")
    tmdb_score_range_label.setObjectName("candidateSearchFilterValue")
    tmdb_score_slider = make_min_threshold_slider(
        0,
        SCORE_SLIDER_MAX,
        "candidateSearchTmdbScoreRange",
        lambda: update_score_range_label(tmdb_score_slider, tmdb_score_range_label),
    )
    add_threshold_filter_row(form, "Мин. TMDb", tmdb_score_range_label, tmdb_score_slider)

    tmdb_votes_range_label = QLabel("")
    tmdb_votes_range_label.setObjectName("candidateSearchFilterValue")
    tmdb_votes_slider = make_min_threshold_slider(
        0,
        VOTES_SLIDER_MAX_INDEX,
        "candidateSearchTmdbVotesRange",
        lambda: update_votes_range_label(tmdb_votes_slider, tmdb_votes_range_label),
    )
    add_threshold_filter_row(form, "Мин. голосов TMDb", tmdb_votes_range_label, tmdb_votes_slider)

    only_complete_check = QCheckBox("Только complete")
    only_complete_check.setObjectName("candidateSearchOnlyComplete")
    only_complete_check.setChecked(DEFAULT_BROWSE_FILTERS["only_complete"])
    only_unwatched_check = QCheckBox("Скрывать просмотренные")
    only_unwatched_check.setObjectName("candidateSearchOnlyUnwatched")
    only_unwatched_check.setChecked(DEFAULT_BROWSE_FILTERS["only_unwatched"])
    hide_hidden_check = QCheckBox("Скрывать hidden")
    hide_hidden_check.setObjectName("candidateSearchHideHidden")
    hide_hidden_check.setChecked(DEFAULT_BROWSE_FILTERS["hide_hidden"])
    form.addWidget(only_complete_check)
    form.addWidget(only_unwatched_check)
    form.addWidget(hide_hidden_check)

    scroll.setWidget(form_host)

    return FiltersFormWidgets(
        scroll=scroll,
        country_selector=country_selector,
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
