"""Score/year/genre filter widgets for the watched sidebar."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from desktop.i18n import tr
from desktop.shared.widgets.range_slider import RangeSlider
from desktop.theme.scaling import layout_px
from desktop.watched.model import (
    MEDIA_FILTER_OPTIONS,
    USER_SCORE_MAX,
    USER_SCORE_MIN,
    USER_SCORE_STEP,
    YEAR_FILTER_DEFAULT_FROM,
    YEAR_FILTER_DEFAULT_TO,
    YEAR_FILTER_MAX,
    YEAR_FILTER_MIN,
    WatchedEntry,
    format_watched_filters_label,
    genre_filter_is_active,
    get_available_genres,
    media_type_filter_is_active,
    score_filter_is_active,
    watched_filters_are_active,
    year_filter_is_active,
)


class WatchedFiltersPanel:
    """Collapsible score/year/genre filters for WatchedTabView."""

    def __init__(
        self,
        entries: list[WatchedEntry],
        *,
        on_filters_changed: Callable[[], None],
    ) -> None:
        self._on_filters_changed = on_filters_changed
        self._entries = entries
        self._expanded = False

        self.toggle = QPushButton(format_watched_filters_label(is_expanded=False))
        self.toggle.setObjectName("watchedFilterToggle")
        self.toggle.clicked.connect(self.toggle_panel)

        self.panel = self._build_panel()
        self.panel.setVisible(False)

    def toggle_panel(self) -> None:
        self._expanded = not self._expanded
        self.panel.setVisible(self._expanded)
        self.update_toggle_label()

    def update_toggle_label(self) -> None:
        score_active = self.score_filter_active()
        year_active = self.year_filter_active()
        genre_active = self.genre_filter_active()
        media_type_active = self.media_type_filter_active()
        filters_active = watched_filters_are_active(score_active, year_active, genre_active, media_type_active)
        self.toggle.setText(
            format_watched_filters_label(
                score_active,
                year_active,
                genre_active,
                is_expanded=self._expanded,
                has_media_type_filter=media_type_active,
            )
        )
        self.toggle.setProperty("watchedFiltersActive", "true" if filters_active else "false")
        self.toggle.style().unpolish(self.toggle)
        self.toggle.style().polish(self.toggle)

    def reset_all(self) -> None:
        self._score_slider.blockSignals(True)
        self._score_slider.setValues(
            self._score_to_slider_value(USER_SCORE_MIN),
            self._score_to_slider_value(USER_SCORE_MAX),
        )
        self._score_slider.blockSignals(False)

        self._year_slider.blockSignals(True)
        self._year_slider.setValues(YEAR_FILTER_DEFAULT_FROM, YEAR_FILTER_DEFAULT_TO)
        self._year_slider.blockSignals(False)

        self._genre_combo.blockSignals(True)
        self._genre_combo.setCurrentIndex(0)
        self._genre_combo.blockSignals(False)

        self._media_type_combo.blockSignals(True)
        self._media_type_combo.setCurrentIndex(0)
        self._media_type_combo.blockSignals(False)

        self._update_score_range_label()
        self._update_year_range_label()
        self._on_filters_changed()

    def reload_genre_options(self, entries: list[WatchedEntry]) -> None:
        self._entries = entries
        current = self.selected_genre()
        self._genre_combo.blockSignals(True)
        self._genre_combo.clear()
        self._genre_combo.addItem(tr("filters.watched.all_genres"), None)
        for genre in get_available_genres(self._entries):
            self._genre_combo.addItem(genre, genre)
        if current is not None:
            index = self._genre_combo.findData(current)
            self._genre_combo.setCurrentIndex(index if index >= 0 else 0)
        else:
            self._genre_combo.setCurrentIndex(0)
        self._genre_combo.blockSignals(False)

    def score_filter_range(self) -> tuple[float, float]:
        lower, upper = self._score_slider.values()
        return (self._score_from_slider_value(lower), self._score_from_slider_value(upper))

    def year_filter_range(self) -> tuple[int, int]:
        return self._year_slider.values()

    def selected_genre(self) -> str | None:
        genre = self._genre_combo.currentData()
        return genre if isinstance(genre, str) else None

    def selected_media_type(self) -> str | None:
        media_type = self._media_type_combo.currentData()
        return media_type if isinstance(media_type, str) else None

    def score_filter_active(self) -> bool:
        min_score, max_score = self.score_filter_range()
        return score_filter_is_active(min_score, max_score)

    def year_filter_active(self) -> bool:
        year_from, year_to = self.year_filter_range()
        return year_filter_is_active(year_from, year_to)

    def genre_filter_active(self) -> bool:
        return genre_filter_is_active(self.selected_genre())

    def media_type_filter_active(self) -> bool:
        return media_type_filter_is_active(self.selected_media_type())

    def _build_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("watchedFiltersPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            layout_px(8),
            layout_px(8),
            layout_px(8),
            layout_px(8),
        )
        layout.setSpacing(layout_px(10))

        layout.addWidget(self._build_score_filter_panel())
        layout.addWidget(self._build_year_filter_panel())
        layout.addWidget(self._build_media_type_filter_panel())
        layout.addWidget(self._build_genre_filter_panel())

        reset_all_button = QPushButton(tr("watched.filters.reset_all"))
        reset_all_button.setObjectName("watchedFilterResetAll")
        reset_all_button.clicked.connect(self.reset_all)
        layout.addWidget(reset_all_button)
        return frame

    def _build_score_filter_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("watchedScoreFilter")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            layout_px(12),
            layout_px(10),
            layout_px(12),
            layout_px(12),
        )
        layout.setSpacing(layout_px(10))

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(layout_px(8))
        title = QLabel(tr("watched.filters.score"))
        title.setObjectName("watchedScoreFilterTitle")
        header_row.addWidget(title)
        header_row.addStretch()

        self._score_range_label = QLabel()
        self._score_range_label.setObjectName("watchedFilterValue")
        header_row.addWidget(self._score_range_label)
        layout.addLayout(header_row)

        self._score_slider = RangeSlider(
            self._score_to_slider_value(USER_SCORE_MIN),
            self._score_to_slider_value(USER_SCORE_MAX),
            self._score_to_slider_value(USER_SCORE_MIN),
            self._score_to_slider_value(USER_SCORE_MAX),
        )
        self._score_slider.setObjectName("watchedScoreRange")
        self._score_slider.rangeChanged.connect(self._on_score_range_changed)
        layout.addWidget(self._score_slider)
        self._update_score_range_label()
        return frame

    def _build_year_filter_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("watchedYearFilter")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            layout_px(12),
            layout_px(10),
            layout_px(12),
            layout_px(12),
        )
        layout.setSpacing(layout_px(10))

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(layout_px(8))
        title = QLabel(tr("watched.filters.year"))
        title.setObjectName("watchedYearFilterTitle")
        header_row.addWidget(title)
        header_row.addStretch()

        self._year_range_label = QLabel()
        self._year_range_label.setObjectName("watchedFilterValue")
        header_row.addWidget(self._year_range_label)
        layout.addLayout(header_row)

        self._year_slider = RangeSlider(
            YEAR_FILTER_MIN,
            YEAR_FILTER_MAX,
            YEAR_FILTER_DEFAULT_FROM,
            YEAR_FILTER_DEFAULT_TO,
        )
        self._year_slider.setObjectName("watchedYearRange")
        self._year_slider.rangeChanged.connect(self._on_year_range_changed)
        layout.addWidget(self._year_slider)
        self._update_year_range_label()
        return frame

    def _build_media_type_filter_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("watchedMediaTypeFilter")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            layout_px(12),
            layout_px(10),
            layout_px(12),
            layout_px(12),
        )
        layout.setSpacing(layout_px(10))

        title = QLabel(tr("watched.filters.media_type"))
        title.setObjectName("watchedMediaTypeFilterTitle")
        layout.addWidget(title)

        self._media_type_combo = QComboBox()
        self._media_type_combo.setObjectName("watchedMediaType")
        for label_key, value in MEDIA_FILTER_OPTIONS:
            self._media_type_combo.addItem(tr(label_key), value)
        self._media_type_combo.currentIndexChanged.connect(self._on_filters_changed)
        layout.addWidget(self._media_type_combo)
        return frame

    def _build_genre_filter_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("watchedGenreFilter")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            layout_px(12),
            layout_px(10),
            layout_px(12),
            layout_px(12),
        )
        layout.setSpacing(layout_px(10))

        title = QLabel(tr("watched.filters.genre"))
        title.setObjectName("watchedGenreFilterTitle")
        layout.addWidget(title)

        self._genre_combo = QComboBox()
        self._genre_combo.setObjectName("watchedGenre")
        self._genre_combo.addItem(tr("filters.watched.all_genres"), None)
        for genre in get_available_genres(self._entries):
            self._genre_combo.addItem(genre, genre)
        self._genre_combo.currentIndexChanged.connect(self._on_filters_changed)
        layout.addWidget(self._genre_combo)
        return frame

    def _score_to_slider_value(self, score: float) -> int:
        return int(round(float(score) / USER_SCORE_STEP))

    def _score_from_slider_value(self, value: int) -> float:
        return round(value * USER_SCORE_STEP, 1)

    def _update_score_range_label(self) -> None:
        min_score, max_score = self.score_filter_range()
        self._score_range_label.setText(f"{min_score:.1f}-{max_score:.1f}")

    def _on_score_range_changed(self, _lower: int, _upper: int) -> None:
        self._update_score_range_label()
        self._on_filters_changed()

    def _update_year_range_label(self) -> None:
        year_from, year_to = self.year_filter_range()
        self._year_range_label.setText(f"{year_from}-{year_to}")

    def _on_year_range_changed(self, _lower: int, _upper: int) -> None:
        self._update_year_range_label()
        self._on_filters_changed()
