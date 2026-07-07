"""Compact read-only summary card for add-title preview dialogs."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from desktop.shared.detail.card_pills import clear_layout, make_pill_label
from desktop.shared.detail.card_poster import (
    cover_crop_poster_pixmap_for_display,
    load_detail_poster_source_pixmap,
)
from desktop.shared.detail.main_info import build_title_meta_text
from desktop.shared.detail.posters import resolve_local_poster_path
from desktop.shared.detail.presenters import (
    build_detail_info_pill_labels,
    build_final_score_star_item,
    build_meta_pill_items,
)
from desktop.shared.detail.rating_indicator import RatingCircleIndicator, StarRatingIndicator
from desktop.shared.detail.types import DetailEntry
from desktop.theme import (
    ADD_TITLE_COMPACT_CONTENT_GAP,
    ADD_TITLE_COMPACT_POSTER_HEIGHT,
    ADD_TITLE_COMPACT_POSTER_RADIUS,
    ADD_TITLE_COMPACT_POSTER_WIDTH,
    ADD_TITLE_COMPACT_SCORE_CIRCLE_DIAMETER,
    ADD_TITLE_COMPACT_SCORE_WIDGET_SIZE,
    FONT_RATING_LABEL_POINT,
    FONT_RATING_VALUE_POINT,
    TRANSPARENT_STYLE,
    build_poster_image_style,
    build_poster_placeholder_style,
    font_px,
    layout_px,
    poster_px,
)

MAX_VISIBLE_GENRE_PILLS = 3


class AddTitleCompactPreviewCard:
    """Add-flow specific card that shows only confirmation-critical summary data."""

    def __init__(self, parent=None) -> None:
        self._local_poster_path: str | None = None

        self._poster_width = poster_px(ADD_TITLE_COMPACT_POSTER_WIDTH)
        self._poster_height = poster_px(ADD_TITLE_COMPACT_POSTER_HEIGHT)
        self._poster_radius = poster_px(ADD_TITLE_COMPACT_POSTER_RADIUS)
        self._score_widget_size = layout_px(ADD_TITLE_COMPACT_SCORE_WIDGET_SIZE)
        self._score_circle_diameter = layout_px(ADD_TITLE_COMPACT_SCORE_CIRCLE_DIAMETER)

        self._frame = QWidget(parent)
        self._frame.setObjectName("addTitleCompactPreviewCard")
        self._frame.setStyleSheet(TRANSPARENT_STYLE)
        self._frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        root = QHBoxLayout(self._frame)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._summary_widget = QWidget()
        self._summary_widget.setObjectName("addTitleCompactSummary")
        self._summary_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._summary_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        summary_row = QHBoxLayout(self._summary_widget)
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(layout_px(ADD_TITLE_COMPACT_CONTENT_GAP))

        self._poster_label = QLabel("Нет постера")
        self._poster_label.setObjectName("addTitleCompactPoster")
        self._poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster_label.setFixedSize(self._poster_width, self._poster_height)
        self._poster_label.setScaledContents(False)
        self._poster_label.setStyleSheet(build_poster_placeholder_style())

        self._info_column_widget = QWidget()
        self._info_column_widget.setObjectName("addTitleCompactInfoColumn")
        self._info_column_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._info_column_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        info_column = QVBoxLayout(self._info_column_widget)
        info_column.setContentsMargins(0, 0, 0, 0)
        info_column.setSpacing(layout_px(9))

        self._title_label = QLabel("")
        self._title_label.setObjectName("addTitleCompactTitle")
        self._title_label.setWordWrap(True)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self._meta_label = QLabel("")
        self._meta_label.setObjectName("addTitleCompactMeta")
        self._meta_label.setWordWrap(True)
        self._meta_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self._genre_row_widget = QWidget()
        self._genre_row_widget.setObjectName("addTitleCompactGenres")
        self._genre_row_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._genre_row_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        self._genre_row = QHBoxLayout(self._genre_row_widget)
        self._genre_row.setContentsMargins(0, 0, 0, 0)
        self._genre_row.setSpacing(layout_px(8))

        self._rating_row_widget = QWidget()
        self._rating_row_widget.setObjectName("addTitleCompactRatings")
        self._rating_row_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._rating_row_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        self._rating_row = QHBoxLayout(self._rating_row_widget)
        self._rating_row.setContentsMargins(0, 0, 0, 0)
        self._rating_row.setSpacing(layout_px(18))

        info_column.addWidget(self._title_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        info_column.addWidget(self._meta_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        info_column.addWidget(self._genre_row_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        info_column.addWidget(self._rating_row_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        info_column.addStretch(1)

        summary_row.addWidget(self._poster_label, alignment=Qt.AlignmentFlag.AlignTop)
        summary_row.addWidget(self._info_column_widget, alignment=Qt.AlignmentFlag.AlignTop)
        root.addStretch(1)
        root.addWidget(self._summary_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addStretch(1)

    @property
    def widget(self):
        return self._frame

    def show_entry(self, entry: DetailEntry) -> None:
        _, movie, card = entry
        self._title_label.setText(str(card.get("title") or entry[0] or "Без названия"))
        self._set_meta_text(build_title_meta_text(card))
        self._set_genres(build_detail_info_pill_labels(card))
        self._set_rating_items(build_meta_pill_items(card), build_final_score_star_item(card))
        self._set_poster(movie, card)

    def _set_meta_text(self, text: str) -> None:
        value = str(text or "").strip()
        self._meta_label.setText(value)
        self._meta_label.setVisible(value != "")

    def _set_genres(self, genres: list[str]) -> None:
        clear_layout(self._genre_row)
        labels = [str(item).strip() for item in genres if str(item).strip()]
        if len(labels) > MAX_VISIBLE_GENRE_PILLS:
            labels = labels[: MAX_VISIBLE_GENRE_PILLS - 1] + [f"+{len(labels) - MAX_VISIBLE_GENRE_PILLS + 1}"]
        self._genre_row.addStretch(1)
        for label in labels:
            pill = make_pill_label(label, "addTitleCompactGenrePill")
            pill.setFixedHeight(layout_px(30))
            self._genre_row.addWidget(pill)
        self._genre_row.addStretch(1)
        self._genre_row_widget.setVisible(len(labels) > 0)

    def _set_rating_items(self, meta_pills: list[dict], star_item: dict | None) -> None:
        clear_layout(self._rating_row)
        has_rating = False
        self._rating_row.addStretch(1)
        tmdb_items = [item for item in meta_pills if item.get("source") == "tmdb"]
        if tmdb_items:
            item = tmdb_items[0]
            ring = RatingCircleIndicator(
                item.get("display_label") or "TMDb",
                item.get("score"),
                item.get("accent"),
                display_value=item.get("display_value"),
                display_label=item.get("display_label") or "TMDb",
                ring_progress=item.get("ring_progress"),
                widget_size=self._score_widget_size,
                circle_diameter=self._score_circle_diameter,
                value_font_point=font_px(FONT_RATING_VALUE_POINT),
                label_font_point=font_px(FONT_RATING_LABEL_POINT),
            )
            ring.setObjectName("addTitleCompactTmdbRing")
            self._rating_row.addWidget(ring, alignment=Qt.AlignmentFlag.AlignVCenter)
            has_rating = True

        if star_item is not None:
            stars = StarRatingIndicator(star_size=layout_px(26), star_gap=layout_px(5))
            stars.setObjectName("addTitleCompactStars")
            stars.set_stars(star_item.get("stars"), star_item.get("tooltip") or "")
            self._rating_row.addWidget(stars, alignment=Qt.AlignmentFlag.AlignVCenter)
            has_rating = True

        self._rating_row.addStretch(1)
        self._rating_row_widget.setVisible(has_rating)

    def _set_poster(self, movie: dict, card: dict) -> None:
        poster_path = resolve_local_poster_path(movie, card)
        self._local_poster_path = poster_path
        self._poster_label.setToolTip(poster_path or "")
        if poster_path not in (None, ""):
            pixmap = load_detail_poster_source_pixmap(str(poster_path))
            if pixmap is not None:
                display_pixmap = cover_crop_poster_pixmap_for_display(
                    pixmap,
                    self._poster_width,
                    self._poster_height,
                    self._poster_radius,
                )
                self._poster_label.setPixmap(display_pixmap)
                self._poster_label.setText("")
                self._poster_label.setStyleSheet(build_poster_image_style())
                return

        self._poster_label.setPixmap(QPixmap())
        self._poster_label.setText("Нет постера")
        self._poster_label.setStyleSheet(build_poster_placeholder_style())
