"""WatchedDetailCard widget for watched, candidate and add-title flows."""

from __future__ import annotations

from desktop.shared.detail.card_pills import clear_layout, fill_meta_pill_row, fill_pill_rows
from desktop.shared.detail.card_poster import DetailCardPosterMixin
from desktop.shared.detail.main_info import build_main_info_items
from desktop.shared.detail.posters import resolve_local_poster_path
from desktop.shared.detail.presenters import (
    build_detail_info_pill_labels,
    build_meta_pill_items,
)
from desktop.shared.detail.profiles import (
    DETAIL_CARD_LAYOUT_PROFILE,
    DETAIL_CARD_STYLE,
    DetailCardLayoutProfile,
    POSTER_PLACEHOLDER_STYLE,
)
from desktop.shared.detail.rating_indicator import RatingCircleIndicator
from desktop.shared.detail.types import DetailEntry
from desktop.theme import (
    COLOR_ACCENT,
    OVERVIEW_DIVIDER_TEXT_SPACING,
    OVERVIEW_SECTION_TOP_SPACING,
    OVERVIEW_TITLE_DIVIDER_SPACING,
    TRANSPARENT_STYLE,
)


class WatchedDetailCard(DetailCardPosterMixin):
    """Detail card widget for the selected watched title."""

    def __init__(self, parent=None, profile: DetailCardLayoutProfile | None = None) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import (
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QSizePolicy,
            QVBoxLayout,
            QWidget,
        )

        self._profile = profile or DETAIL_CARD_LAYOUT_PROFILE
        self._poster_source_pixmap = None
        self._local_poster_path: str | None = None
        self._mark_watched_handler = None
        self._hide_handler = None
        self._mark_watched_button = None
        self._hide_button = None
        card = self

        class DetailCardFrame(QFrame):
            def resizeEvent(self, event) -> None:
                super().resizeEvent(event)
                card._schedule_poster_height_sync()

        self._frame = DetailCardFrame(parent)
        self._frame.setObjectName("detailCard")
        self._frame.setStyleSheet(DETAIL_CARD_STYLE)
        self._frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        root = QVBoxLayout(self._frame)
        root.setContentsMargins(
            self._profile.card_padding,
            self._profile.card_padding,
            self._profile.card_padding,
            self._profile.card_padding,
        )
        root.setSpacing(OVERVIEW_SECTION_TOP_SPACING)

        top_row = QHBoxLayout()
        top_row.setSpacing(self._profile.poster_row_spacing)

        self._poster_label = QLabel("Нет постера")
        self._poster_label.setObjectName("detailPoster")
        self._poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster_label.setFixedSize(self._profile.poster_width, self._profile.poster_height)
        self._poster_label.setScaledContents(False)
        self._poster_label.setStyleSheet(POSTER_PLACEHOLDER_STYLE)
        self._poster_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._poster_label.customContextMenuRequested.connect(self._show_poster_context_menu)

        self._info_column_widget = QWidget()
        self._info_column_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._info_column_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        info_column = QVBoxLayout(self._info_column_widget)
        info_column.setContentsMargins(0, 0, 0, 0)
        info_column.setSpacing(12)

        self._title_label = QLabel("Выберите тайтл слева")
        self._title_label.setObjectName("detailTitle")
        self._title_label.setWordWrap(True)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._title_label.setMinimumHeight(36)
        self._title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        metrics_row_widget = QWidget()
        metrics_row_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._metrics_row_widget = metrics_row_widget
        self._metrics_row = QHBoxLayout(metrics_row_widget)
        self._metrics_row.setContentsMargins(0, 0, 0, 0)
        self._metrics_row.setSpacing(10)

        self._score_indicator = None
        if self._profile.show_user_score:
            self._score_indicator = RatingCircleIndicator(
                "моя",
                None,
                COLOR_ACCENT,
                widget_size=self._profile.rating_widget_size,
                circle_diameter=self._profile.rating_circle_diameter,
                value_font_point=self._profile.rating_value_font_point,
                label_font_point=self._profile.rating_label_font_point,
            )

        self._meta_pills_widget = QWidget()
        self._meta_pills_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._meta_pills_layout = QHBoxLayout(self._meta_pills_widget)
        self._meta_pills_layout.setContentsMargins(0, 0, 0, 0)
        self._meta_pills_layout.setSpacing(10)

        if self._score_indicator is not None:
            self._metrics_row.addWidget(self._score_indicator, alignment=Qt.AlignmentFlag.AlignLeft)
        self._metrics_row.addWidget(self._meta_pills_widget, alignment=Qt.AlignmentFlag.AlignVCenter)
        if self._profile.show_mark_watched_button:
            self._mark_watched_button = QPushButton("👁")
            self._mark_watched_button.setObjectName("candidateMarkWatchedButton")
            self._mark_watched_button.setToolTip("Перенести в просмотренные")
            self._mark_watched_button.setFixedSize(36, 36)
            self._mark_watched_button.setEnabled(False)
            self._mark_watched_button.clicked.connect(self._on_mark_watched_clicked)
            self._metrics_row.addWidget(self._mark_watched_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        if self._profile.show_hide_candidate_button:
            self._hide_button = QPushButton("Hide")
            self._hide_button.setObjectName("candidateHideButton")
            self._hide_button.setToolTip("Скрыть кандидата")
            self._hide_button.setFixedSize(52, 36)
            self._hide_button.setEnabled(False)
            self._hide_button.clicked.connect(self._on_hide_clicked)
            self._metrics_row.addWidget(self._hide_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._metrics_row.addStretch()

        self._genre_section = QWidget()
        self._genre_section.setStyleSheet(TRANSPARENT_STYLE)
        self._genre_pills_layout = QVBoxLayout(self._genre_section)
        self._genre_pills_layout.setContentsMargins(0, 0, 0, 0)
        self._genre_pills_layout.setSpacing(8)

        self._main_info_section = QWidget()
        self._main_info_section.setObjectName("mainInfoSection")
        self._main_info_section.setStyleSheet(TRANSPARENT_STYLE)
        main_info_layout = QVBoxLayout(self._main_info_section)
        main_info_layout.setContentsMargins(0, 0, 0, 0)
        main_info_layout.setSpacing(10)

        self._main_info_divider = QFrame()
        self._main_info_divider.setObjectName("mainInfoDivider")
        self._main_info_divider.setFrameShape(QFrame.Shape.HLine)
        self._main_info_divider.setFixedHeight(1)

        self._main_info_title_label = QLabel("Основная информация")
        self._main_info_title_label.setObjectName("mainInfoTitle")
        self._main_info_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self._main_info_grid_widget = QWidget()
        self._main_info_grid_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._main_info_grid = QGridLayout(self._main_info_grid_widget)
        self._main_info_grid.setContentsMargins(0, 0, 0, 0)
        self._main_info_grid.setHorizontalSpacing(14)
        self._main_info_grid.setVerticalSpacing(6)
        self._main_info_grid.setColumnStretch(0, 0)
        self._main_info_grid.setColumnStretch(1, 1)

        main_info_layout.addWidget(self._main_info_divider)
        main_info_layout.addWidget(self._main_info_title_label)
        main_info_layout.addWidget(self._main_info_grid_widget)

        self._overview_frame = QFrame()
        self._overview_frame.setObjectName("overviewBlock")
        self._overview_frame.setFrameShape(QFrame.Shape.NoFrame)
        self._overview_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        overview_layout = QVBoxLayout(self._overview_frame)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.setSpacing(0)

        self._overview_title_label = QLabel("Описание")
        self._overview_title_label.setObjectName("overviewTitle")
        self._overview_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self._overview_divider = QFrame()
        self._overview_divider.setObjectName("overviewDivider")
        self._overview_divider.setFrameShape(QFrame.Shape.HLine)
        self._overview_divider.setFixedHeight(1)

        self._overview_label = QLabel("")
        self._overview_label.setObjectName("overviewText")
        self._overview_label.setWordWrap(True)
        self._overview_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._overview_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        overview_layout.addWidget(self._overview_title_label)
        overview_layout.addSpacing(OVERVIEW_TITLE_DIVIDER_SPACING)
        overview_layout.addWidget(self._overview_divider)
        overview_layout.addSpacing(OVERVIEW_DIVIDER_TEXT_SPACING)
        overview_layout.addWidget(self._overview_label)

        info_column.addWidget(self._title_label)
        info_column.addSpacing(2)
        info_column.addWidget(self._genre_section)
        info_column.addSpacing(2)
        info_column.addWidget(metrics_row_widget)
        info_column.addSpacing(6)
        info_column.addWidget(self._main_info_section)

        top_row.addWidget(self._poster_label, alignment=Qt.AlignmentFlag.AlignTop)
        top_row.addWidget(self._info_column_widget, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(top_row)
        root.addWidget(self._overview_frame)
        if self._profile.include_bottom_stretch:
            root.addStretch(1)

    @property
    def widget(self):
        return self._frame

    def set_mark_watched_handler(self, handler) -> None:
        """Optional callback for candidate transfer to watched dataset."""
        self._mark_watched_handler = handler
        if self._mark_watched_button is not None:
            self._mark_watched_button.setEnabled(handler is not None)

    def set_hide_handler(self, handler) -> None:
        """Optional callback for hiding candidate rows."""
        self._hide_handler = handler
        if self._hide_button is not None:
            self._hide_button.setEnabled(handler is not None)

    def _on_mark_watched_clicked(self) -> None:
        if self._mark_watched_handler is not None:
            self._mark_watched_handler()

    def _on_hide_clicked(self) -> None:
        if self._hide_handler is not None:
            self._hide_handler()

    def _metrics_row_should_show(self, meta_pill_count: int) -> bool:
        if self._profile.show_user_score:
            return True
        if meta_pill_count > 0:
            return True
        return self._profile.show_mark_watched_button or self._profile.show_hide_candidate_button

    def _info_column_content_width(self) -> int:
        width = self._info_column_widget.width()
        if width > 0:
            return width
        frame_width = self._frame.width()
        if frame_width <= 0:
            return 0
        return max(
            120,
            frame_width
            - self._profile.poster_width
            - self._profile.poster_row_spacing
            - (2 * self._profile.card_padding),
        )

    def show_empty(self, title: str = "Выберите тайтл слева") -> None:
        self._set_poster_placeholder()
        self._set_local_poster_path(None)
        self._title_label.setText(title)
        if self._score_indicator is not None:
            self._score_indicator.set_score(None)
        fill_meta_pill_row(self._meta_pills_layout, [], self._profile)
        self._meta_pills_widget.setVisible(False)
        fill_pill_rows(self._genre_pills_layout, [], "genrePill")
        self._genre_section.setVisible(False)
        self._overview_label.setText("")
        self._overview_frame.setVisible(False)
        self._set_main_info_items([])
        if self._mark_watched_button is not None:
            self._mark_watched_button.setEnabled(self._mark_watched_handler is not None)
        if self._hide_button is not None:
            self._hide_button.setEnabled(self._hide_handler is not None)
        self._metrics_row_widget.setVisible(self._metrics_row_should_show(0))
        self._schedule_poster_height_sync()

    def show_entry(self, entry: DetailEntry) -> None:
        from desktop.shared.detail.presenters import get_overview_display, has_overview_text

        _, movie, card = entry
        self._title_label.setText(card.get("title") or entry[0])
        if self._score_indicator is not None:
            self._score_indicator.set_score(card.get("user_score"))

        meta_pills = build_meta_pill_items(card)
        fill_meta_pill_row(self._meta_pills_layout, meta_pills, self._profile)
        self._meta_pills_widget.setVisible(len(meta_pills) > 0)
        if self._mark_watched_button is not None:
            self._mark_watched_button.setEnabled(self._mark_watched_handler is not None)
        if self._hide_button is not None:
            self._hide_button.setEnabled(self._hide_handler is not None)
        self._metrics_row_widget.setVisible(self._metrics_row_should_show(len(meta_pills)))

        detail_pills = build_detail_info_pill_labels(card)
        fill_pill_rows(self._genre_pills_layout, detail_pills, "genrePill")
        self._genre_section.setVisible(len(detail_pills) > 0)

        self._set_main_info_items(build_main_info_items(card))

        if has_overview_text(card):
            self._overview_label.setText(get_overview_display(card))
            self._overview_frame.setVisible(True)
        else:
            self._overview_label.setText("")
            self._overview_frame.setVisible(False)

        poster_path = resolve_local_poster_path(movie, card)
        if poster_path is None or self._set_poster_image(poster_path) is False:
            self._set_poster_placeholder()
        self._set_local_poster_path(poster_path)
        self._schedule_poster_height_sync()

    def _set_main_info_items(self, items: list[dict[str, str]]) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QLabel

        clear_layout(self._main_info_grid)
        for row, item in enumerate(items):
            label = QLabel(str(item.get("label", "")))
            label.setObjectName("mainInfoLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

            value = QLabel(str(item.get("value", "")))
            value.setObjectName("mainInfoValue")
            value.setWordWrap(True)
            value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

            self._main_info_grid.addWidget(label, row, 0)
            self._main_info_grid.addWidget(value, row, 1)

        self._main_info_section.setVisible(len(items) > 0)
