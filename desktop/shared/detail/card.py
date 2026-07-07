"""WatchedDetailCard widget for watched, candidate and add-title flows."""

from __future__ import annotations

from typing import Any

from desktop.shared.detail.action_icons import make_detail_action_icon
from desktop.shared.detail import profiles as detail_profiles
from desktop.shared.detail.card_pills import clear_layout, fill_detail_chip_rows, make_meta_pill
from desktop.shared.detail.card_poster import DetailCardPosterMixin
from desktop.shared.detail.main_info import build_main_info_items, build_title_meta_text
from desktop.shared.detail.posters import resolve_local_poster_path
from desktop.shared.detail.presenters import (
    build_detail_info_pill_labels,
    build_final_score_star_item,
    build_meta_pill_items,
    build_user_score_badge_item,
)
from desktop.shared.detail.profiles import DetailCardLayoutProfile
from desktop.shared.detail.rating_indicator import StarRatingIndicator
from desktop.shared.detail.types import DetailEntry
from desktop.theme import (
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    TRANSPARENT_STYLE,
    build_detail_card_style,
    build_poster_image_style,
    build_poster_placeholder_style,
)

RATING_META_PILLS_SPACING = 1
MAIN_INFO_COLLAPSED_ROW_COUNT = 4


class WatchedDetailCard(DetailCardPosterMixin):
    """Detail card widget for the selected watched title."""

    def __init__(self, parent=None, profile: DetailCardLayoutProfile | None = None) -> None:
        from PyQt6.QtCore import QSize, Qt
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

        self._profile = profile or detail_profiles.DETAIL_CARD_LAYOUT_PROFILE
        self._poster_source_pixmap = None
        self._local_poster_path: str | None = None
        self._mark_watched_handler = None
        self._hide_handler = None
        self._mark_watched_button = None
        self._hide_button = None
        self._detail_chip_labels: list[str] = []
        self._main_info_items: list[dict[str, Any]] = []
        self._main_info_expanded = False
        card = self

        class DetailCardFrame(QFrame):
            def resizeEvent(self, event) -> None:
                super().resizeEvent(event)
                card._schedule_poster_height_sync()
                card._schedule_detail_chip_reflow()

        class UserScoreBadgeLabel(QLabel):
            def paintEvent(self, event) -> None:
                from PyQt6.QtCore import QRectF, Qt
                from PyQt6.QtGui import QColor, QPainter, QPen

                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
                radius = rect.height() / 2
                painter.setPen(QPen(QColor(COLOR_TEXT), 1))
                painter.setBrush(QColor(COLOR_TEXT))
                painter.drawRoundedRect(rect, radius, radius)
                painter.end()
                super().paintEvent(event)

        self._frame = DetailCardFrame(parent)
        self._frame.setObjectName("detailHeroCard")
        self._frame.setStyleSheet(build_detail_card_style())
        self._frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        root = QVBoxLayout(self._frame)
        root.setContentsMargins(
            self._profile.detail_hero_card_padding,
            self._profile.detail_hero_card_padding_top,
            self._profile.detail_hero_card_padding,
            self._profile.detail_hero_card_padding,
        )
        root.setSpacing(0)

        self._content_container = QWidget()
        self._content_container.setObjectName("detailContentContainer")
        self._content_container.setStyleSheet(TRANSPARENT_STYLE)
        self._content_container.setMaximumWidth(self._profile.detail_content_max_width)
        self._content_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        content_layout = QVBoxLayout(self._content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._top_row_widget = QWidget()
        self._top_row_widget.setObjectName("detailTopRow")
        self._top_row_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._top_row_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        top_row = QHBoxLayout(self._top_row_widget)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(self._profile.detail_poster_right_gap)

        self._poster_shell = QFrame()
        self._poster_shell.setObjectName("detailPosterShell")
        self._poster_shell.setFixedSize(self._profile.detail_poster_width, self._profile.detail_poster_height)
        self._poster_shell.setFrameShape(QFrame.Shape.NoFrame)
        self._poster_shell.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        poster_shell_layout = QGridLayout(self._poster_shell)
        poster_border_width = self._profile.detail_poster_border_width
        poster_shell_layout.setContentsMargins(
            poster_border_width,
            poster_border_width,
            poster_border_width,
            poster_border_width,
        )
        poster_shell_layout.setSpacing(0)

        self._poster_label = QLabel("Нет постера", self._poster_shell)
        self._poster_label.setObjectName("detailPoster")
        self._poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster_label.setFixedSize(
            self._profile.detail_poster_content_width,
            self._profile.detail_poster_content_height,
        )
        self._poster_label.setScaledContents(False)
        self._poster_label.setStyleSheet(build_poster_placeholder_style())
        self._poster_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._poster_label.customContextMenuRequested.connect(self._show_poster_context_menu)

        self._poster_overlay = QWidget(self._poster_shell)
        self._poster_overlay.setObjectName("detailPosterOverlay")
        self._poster_overlay.setStyleSheet(TRANSPARENT_STYLE)
        self._poster_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._poster_overlay.setFixedSize(
            self._profile.detail_poster_content_width,
            self._profile.detail_poster_content_height,
        )
        poster_overlay_layout = QHBoxLayout(self._poster_overlay)
        poster_overlay_layout.setContentsMargins(
            max(0, self._profile.detail_user_score_badge_left - poster_border_width),
            max(0, self._profile.detail_user_score_badge_top - poster_border_width),
            0,
            0,
        )
        poster_overlay_layout.setSpacing(0)

        self._user_score_badge = UserScoreBadgeLabel("", self._poster_shell)
        self._user_score_badge.setObjectName("detailUserScoreBadge")
        self._user_score_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._user_score_badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._user_score_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._user_score_badge.setAutoFillBackground(True)
        self._user_score_badge.setMinimumWidth(self._profile.detail_user_score_badge_min_width)
        self._user_score_badge.setFixedHeight(self._profile.detail_user_score_badge_height)
        self._user_score_badge.setContentsMargins(
            self._profile.detail_user_score_badge_padding_x,
            0,
            self._profile.detail_user_score_badge_padding_x,
            0,
        )
        self._user_score_badge.hide()

        poster_shell_layout.addWidget(self._poster_label, 0, 0)
        poster_overlay_layout.addWidget(
            self._user_score_badge,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )
        poster_overlay_layout.addStretch(1)
        poster_shell_layout.addWidget(self._poster_overlay, 0, 0)

        self._poster_column_widget = QWidget()
        self._poster_column_widget.setObjectName("detailPosterColumn")
        self._poster_column_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._poster_column_widget.setFixedWidth(self._profile.detail_poster_width)
        self._poster_column_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        poster_column = QVBoxLayout(self._poster_column_widget)
        poster_column.setContentsMargins(0, 0, 0, 0)
        poster_column.setSpacing(self._profile.detail_poster_actions_top_gap)
        poster_column.addWidget(self._poster_shell, alignment=Qt.AlignmentFlag.AlignTop)

        self._info_column_widget = QWidget()
        self._info_column_widget.setObjectName("detailInfoColumn")
        self._info_column_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._info_column_widget.setMinimumWidth(self._profile.detail_info_min_width)
        self._info_column_widget.setMaximumWidth(self._profile.detail_info_column_max_width)
        self._info_column_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum,
        )
        info_column = QVBoxLayout(self._info_column_widget)
        info_column.setContentsMargins(0, self._profile.detail_info_top_offset, 0, 0)
        info_column.setSpacing(self._profile.detail_column_spacing)

        self._title_block_widget = QWidget()
        self._title_block_widget.setObjectName("detailTitleBlock")
        self._title_block_widget.setStyleSheet(TRANSPARENT_STYLE)
        title_block_layout = QVBoxLayout(self._title_block_widget)
        title_block_layout.setContentsMargins(0, 0, 0, 0)
        title_block_layout.setSpacing(self._profile.detail_title_meta_gap)

        self._title_row_widget = QWidget()
        self._title_row_widget.setStyleSheet(TRANSPARENT_STYLE)
        title_row = QHBoxLayout(self._title_row_widget)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(self._profile.detail_small_spacing)

        self._poster_actions_widget = QWidget()
        self._poster_actions_widget.setObjectName("detailPosterActions")
        self._poster_actions_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._poster_actions_layout = QHBoxLayout(self._poster_actions_widget)
        self._poster_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._poster_actions_layout.setSpacing(self._profile.detail_small_spacing)

        self._title_label = QLabel("Выберите тайтл слева")
        self._title_label.setObjectName("detailTitle")
        self._title_label.setWordWrap(True)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._title_label.setMinimumHeight(self._profile.detail_title_min_height)
        self._title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self._title_meta_label = QLabel("")
        self._title_meta_label.setObjectName("detailTitleMeta")
        self._title_meta_label.setWordWrap(True)
        self._title_meta_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._title_meta_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._title_meta_label.hide()

        title_block_layout.addWidget(self._title_row_widget)
        title_block_layout.addWidget(self._title_meta_label)

        score_summary_widget = QWidget()
        score_summary_widget.setObjectName("detailScoreSummaryRow")
        score_summary_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._score_summary_widget = score_summary_widget
        self._score_summary_row = QHBoxLayout(score_summary_widget)
        self._score_summary_row.setContentsMargins(0, 0, 0, 0)
        self._score_summary_row.setSpacing(0)
        score_summary_widget.setMaximumWidth(self._profile.detail_section_max_width)

        self._score_indicator = None

        self._tmdb_ring_slot = QWidget()
        self._tmdb_ring_slot.setObjectName("detailTmdbRingSlot")
        self._tmdb_ring_slot.setStyleSheet(TRANSPARENT_STYLE)
        self._tmdb_ring_slot.setFixedSize(
            self._profile.detail_rating_widget_size,
            self._profile.detail_rating_widget_size,
        )
        self._tmdb_ring_slot.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self._tmdb_ring_layout = QHBoxLayout(self._tmdb_ring_slot)
        self._tmdb_ring_layout.setContentsMargins(0, 0, 0, 0)
        self._tmdb_ring_layout.setSpacing(RATING_META_PILLS_SPACING)

        final_stars_width = 5 * self._profile.detail_star_size + 4 * self._profile.detail_star_gap
        self._final_score_stars_block = QWidget()
        self._final_score_stars_block.setObjectName("detailFinalScoreStars")
        self._final_score_stars_block.setStyleSheet(TRANSPARENT_STYLE)
        self._final_score_stars_block.setFixedWidth(final_stars_width)
        self._final_score_stars_block.setMinimumHeight(
            self._profile.detail_star_size + self._profile.detail_small_spacing
        )
        self._final_score_stars_block.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self._final_score_stars_layout = QHBoxLayout(self._final_score_stars_block)
        self._final_score_stars_layout.setContentsMargins(0, 0, 0, 0)
        self._final_score_stars_layout.setSpacing(0)

        self._rating_stars_widget = StarRatingIndicator(
            star_size=self._profile.detail_star_size,
            star_gap=self._profile.detail_star_gap,
        )
        self._rating_stars_widget.setObjectName("detailFinalScoreStarsWidget")
        self._final_score_stars_layout.addWidget(
            self._rating_stars_widget,
            alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )

        self._final_score_stars_lane = QWidget()
        self._final_score_stars_lane.setObjectName("detailFinalScoreStarsLane")
        self._final_score_stars_lane.setStyleSheet(TRANSPARENT_STYLE)
        self._final_score_stars_lane.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self._final_score_stars_lane_layout = QHBoxLayout(self._final_score_stars_lane)
        self._final_score_stars_lane_layout.setContentsMargins(0, 0, 0, 0)
        self._final_score_stars_lane_layout.setSpacing(0)
        self._final_score_stars_lane_layout.addStretch(1)
        self._final_score_stars_lane_layout.addWidget(
            self._final_score_stars_block,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        self._final_score_stars_lane_layout.addStretch(1)

        self._score_summary_row.addWidget(
            self._tmdb_ring_slot,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        self._score_summary_row.addWidget(
            self._final_score_stars_lane,
            stretch=1,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        if self._profile.show_mark_watched_button:
            self._mark_watched_button = QPushButton()
            self._mark_watched_button.setObjectName("candidateMarkWatchedButton")
            self._mark_watched_button.setToolTip("Перенести в просмотренные")
            self._mark_watched_button.setIcon(
                make_detail_action_icon("eye", COLOR_TEXT, COLOR_TEXT_SECONDARY)
            )
            self._mark_watched_button.setIconSize(
                QSize(
                    self._profile.detail_candidate_action_icon_size,
                    self._profile.detail_candidate_action_icon_size,
                )
            )
            self._mark_watched_button.setFixedSize(
                self._profile.detail_candidate_action_button_size,
                self._profile.detail_candidate_action_button_size,
            )
            self._mark_watched_button.setEnabled(False)
            self._mark_watched_button.clicked.connect(self._on_mark_watched_clicked)
            self._poster_actions_layout.addWidget(
                self._mark_watched_button,
                alignment=Qt.AlignmentFlag.AlignLeft,
            )
        if self._profile.show_hide_candidate_button:
            self._hide_button = QPushButton()
            self._hide_button.setObjectName("candidateHideButton")
            self._hide_button.setToolTip("Скрыть кандидата")
            self._hide_button.setIcon(
                make_detail_action_icon("hide", COLOR_TEXT, COLOR_TEXT_SECONDARY)
            )
            self._hide_button.setIconSize(
                QSize(
                    self._profile.detail_candidate_action_icon_size,
                    self._profile.detail_candidate_action_icon_size,
                )
            )
            self._hide_button.setFixedSize(
                self._profile.detail_candidate_action_button_size,
                self._profile.detail_candidate_action_button_size,
            )
            self._hide_button.setEnabled(False)
            self._hide_button.clicked.connect(self._on_hide_clicked)
            self._poster_actions_layout.addWidget(
                self._hide_button,
                alignment=Qt.AlignmentFlag.AlignLeft,
            )
        self._poster_actions_layout.addStretch(1)
        self._poster_actions_widget.setVisible(
            self._profile.show_mark_watched_button or self._profile.show_hide_candidate_button
        )
        title_row.addWidget(self._title_label, stretch=1)
        poster_column.addWidget(self._poster_actions_widget)

        self._genre_section = QWidget()
        self._genre_section.setObjectName("detailChipsContainer")
        self._genre_section.setStyleSheet(TRANSPARENT_STYLE)
        self._genre_pills_layout = QVBoxLayout(self._genre_section)
        self._genre_pills_layout.setContentsMargins(0, 0, 0, 0)
        self._genre_pills_layout.setSpacing(self._profile.detail_chip_row_gap)

        self._main_info_section = QWidget()
        self._main_info_section.setObjectName("detailMainInfoSection")
        self._main_info_section.setStyleSheet(TRANSPARENT_STYLE)
        self._main_info_section.setMaximumWidth(self._profile.detail_section_max_width)
        self._main_info_section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        main_info_layout = QVBoxLayout(self._main_info_section)
        main_info_layout.setContentsMargins(0, 0, 0, 0)
        main_info_layout.setSpacing(self._profile.detail_main_info_header_panel_gap)

        self._main_info_header_widget = QWidget()
        self._main_info_header_widget.setStyleSheet(TRANSPARENT_STYLE)
        main_info_header_layout = QHBoxLayout(self._main_info_header_widget)
        main_info_header_layout.setContentsMargins(0, 0, 0, 0)
        main_info_header_layout.setSpacing(self._profile.detail_column_spacing)

        self._main_info_divider = QFrame()
        self._main_info_divider.setObjectName("detailMainInfoHeaderDivider")
        self._main_info_divider.setFrameShape(QFrame.Shape.HLine)
        self._main_info_divider.setFixedHeight(self._profile.detail_divider_height)
        self._main_info_divider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._main_info_title_label = QLabel("ОСНОВНАЯ ИНФОРМАЦИЯ")
        self._main_info_title_label.setObjectName("detailMainInfoHeader")
        self._main_info_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self._main_info_toggle_button = QPushButton("Показать больше")
        self._main_info_toggle_button.setObjectName("detailMainInfoToggleButton")
        self._main_info_toggle_button.setAutoDefault(False)
        self._main_info_toggle_button.setDefault(False)
        self._main_info_toggle_button.clicked.connect(self._toggle_main_info_expanded)
        self._main_info_toggle_button.hide()

        main_info_header_layout.addWidget(self._main_info_title_label)
        main_info_header_layout.addWidget(self._main_info_toggle_button)
        main_info_header_layout.addWidget(self._main_info_divider, stretch=1)

        self._main_info_panel = QFrame()
        self._main_info_panel.setObjectName("detailMainInfoPanel")
        self._main_info_panel.setFrameShape(QFrame.Shape.NoFrame)
        self._main_info_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._main_info_grid = QGridLayout(self._main_info_panel)
        main_info_padding_y = min(
            self._profile.detail_main_info_panel_padding_y,
            self._profile.detail_main_info_compact_padding_y_cap,
        )
        self._main_info_grid.setContentsMargins(
            self._profile.detail_main_info_panel_padding_x,
            main_info_padding_y,
            self._profile.detail_main_info_panel_padding_x,
            main_info_padding_y,
        )
        self._main_info_grid.setHorizontalSpacing(self._profile.detail_chip_col_gap)
        self._main_info_grid.setVerticalSpacing(self._profile.detail_main_info_row_gap)
        self._main_info_grid.setColumnStretch(0, 0)
        self._main_info_grid.setColumnStretch(1, 1)

        main_info_layout.addWidget(self._main_info_header_widget)
        main_info_layout.addWidget(self._main_info_panel)

        self._overview_frame = QFrame()
        self._overview_frame.setObjectName("detailOverviewSection")
        self._overview_frame.setFrameShape(QFrame.Shape.NoFrame)
        self._overview_frame.setFixedWidth(self._profile.detail_poster_width)
        self._overview_frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        overview_layout = QVBoxLayout(self._overview_frame)
        overview_layout.setContentsMargins(self._profile.detail_overview_left_inset, 0, 0, 0)
        overview_layout.setSpacing(0)

        self._overview_divider = QFrame()
        self._overview_divider.setObjectName("detailOverviewDivider")
        self._overview_divider.setFrameShape(QFrame.Shape.HLine)
        self._overview_divider.setFixedHeight(self._profile.detail_divider_height)
        self._overview_divider.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._overview_title_label = QLabel("ОПИСАНИЕ")
        self._overview_title_label.setObjectName("detailOverviewHeader")
        self._overview_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self._overview_label = QLabel("")
        self._overview_label.setObjectName("detailOverviewText")
        self._overview_label.setWordWrap(True)
        self._overview_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._overview_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        overview_layout.addWidget(self._overview_divider)
        overview_layout.addSpacing(self._profile.detail_overview_title_top_gap)
        overview_layout.addWidget(self._overview_title_label)
        overview_layout.addSpacing(self._profile.detail_overview_text_top_gap)
        overview_layout.addWidget(self._overview_label)
        self._overview_frame.hide()

        self._overview_gap_widget = QWidget()
        self._overview_gap_widget.setObjectName("detailOverviewTopGap")
        self._overview_gap_widget.setStyleSheet(TRANSPARENT_STYLE)
        self._overview_gap_widget.setFixedHeight(self._profile.detail_overview_top_gap)
        self._overview_gap_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._overview_gap_widget.hide()
        poster_column.addWidget(self._overview_gap_widget)
        poster_column.addWidget(self._overview_frame, alignment=Qt.AlignmentFlag.AlignLeft)
        poster_column.addStretch(1)

        info_column.addWidget(self._title_block_widget)
        info_column.addSpacing(self._profile.detail_title_chips_gap)
        info_column.addWidget(self._genre_section)
        info_column.addSpacing(self._profile.detail_micro_spacing)
        info_column.addWidget(score_summary_widget)
        info_column.addSpacing(self._profile.detail_section_spacing)
        info_column.addWidget(self._main_info_section)

        top_row.addWidget(self._poster_column_widget, alignment=Qt.AlignmentFlag.AlignTop)
        top_row.addWidget(self._info_column_widget, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        content_layout.addWidget(self._top_row_widget)
        if self._profile.include_bottom_stretch:
            content_layout.addStretch(1)

        self._content_center_row = QWidget()
        self._content_center_row.setObjectName("detailContentCenterRow")
        self._content_center_row.setStyleSheet(TRANSPARENT_STYLE)
        self._content_center_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        content_center_layout = QHBoxLayout(self._content_center_row)
        content_center_layout.setContentsMargins(0, 0, 0, 0)
        content_center_layout.setSpacing(0)
        content_center_layout.addStretch(1)
        content_center_layout.addWidget(self._content_container)
        content_center_layout.addStretch(1)

        root.addWidget(
            self._content_center_row,
            alignment=Qt.AlignmentFlag.AlignTop,
        )

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

    def _score_summary_should_show(self, has_tmdb_ring: bool, has_final_stars: bool) -> bool:
        if has_tmdb_ring or has_final_stars:
            return True
        return False

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
            - self._profile.detail_poster_width
            - self._profile.detail_poster_right_gap
            - (2 * self._profile.detail_hero_card_padding),
        )

    def _schedule_detail_chip_reflow(self) -> None:
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._refresh_detail_chips)

    def _refresh_detail_chips(self) -> None:
        if len(self._detail_chip_labels) == 0:
            clear_layout(self._genre_pills_layout)
            self._genre_section.setVisible(False)
            self._genre_section.setFixedHeight(0)
            return

        fill_detail_chip_rows(
            self._genre_pills_layout,
            self._detail_chip_labels,
            self._info_column_content_width(),
            "genrePill",
            self._profile,
        )
        row_count = min(self._profile.detail_chip_max_rows, self._genre_pills_layout.count())
        if row_count <= 0:
            self._genre_section.setVisible(False)
            self._genre_section.setFixedHeight(0)
            return

        height = (
            self._profile.detail_chip_height * row_count
            + self._profile.detail_chip_row_gap * max(0, row_count - 1)
        )
        self._genre_section.setFixedHeight(height)
        self._genre_section.setVisible(True)

    def show_empty(self, title: str = "Выберите тайтл слева") -> None:
        self._set_poster_placeholder()
        self._set_local_poster_path(None)
        self._title_label.setText(title)
        self._set_title_meta("")
        self._set_user_score_badge(None)
        self._set_score_summary_items([], None)
        self._detail_chip_labels = []
        self._refresh_detail_chips()
        self._overview_label.setText("")
        self._overview_frame.setVisible(False)
        self._overview_gap_widget.setVisible(False)
        self._main_info_expanded = False
        self._set_main_info_items([])
        if self._mark_watched_button is not None:
            self._mark_watched_button.setEnabled(self._mark_watched_handler is not None)
        if self._hide_button is not None:
            self._hide_button.setEnabled(self._hide_handler is not None)
        self._schedule_poster_height_sync()

    def show_entry(self, entry: DetailEntry) -> None:
        from desktop.shared.detail.presenters import get_overview_display, has_overview_text

        _, movie, card = entry
        self._title_label.setText(card.get("title") or entry[0])
        self._set_title_meta(build_title_meta_text(card))
        self._set_user_score_badge(build_user_score_badge_item(card))

        meta_pills = build_meta_pill_items(card)
        star_item = build_final_score_star_item(card)
        self._set_score_summary_items(meta_pills, star_item)
        if self._mark_watched_button is not None:
            self._mark_watched_button.setEnabled(self._mark_watched_handler is not None)
        if self._hide_button is not None:
            self._hide_button.setEnabled(self._hide_handler is not None)

        detail_pills = build_detail_info_pill_labels(card)
        self._detail_chip_labels = detail_pills
        self._refresh_detail_chips()

        self._main_info_expanded = False
        self._set_main_info_items(build_main_info_items(card))

        if has_overview_text(card):
            self._overview_label.setText(get_overview_display(card))
            self._overview_gap_widget.setVisible(True)
            self._overview_frame.setVisible(True)
        else:
            self._overview_label.setText("")
            self._overview_gap_widget.setVisible(False)
            self._overview_frame.setVisible(False)

        poster_path = resolve_local_poster_path(movie, card)
        if poster_path is None or self._set_poster_image(poster_path) is False:
            self._set_poster_placeholder()
        self._set_local_poster_path(poster_path)
        self._schedule_poster_height_sync()

    def _set_title_meta(self, text: str) -> None:
        value = str(text or "").strip()
        self._title_meta_label.setText(value)
        self._title_meta_label.setVisible(value != "")

    def _set_score_summary_items(self, meta_pills: list[dict], star_item: dict | None) -> None:
        from PyQt6.QtCore import Qt

        clear_layout(self._tmdb_ring_layout)
        tmdb_ring_items = [item for item in meta_pills if item.get("source") == "tmdb"]
        has_tmdb_ring = len(tmdb_ring_items) > 0
        if has_tmdb_ring:
            self._tmdb_ring_layout.addStretch(1)
            self._tmdb_ring_layout.addWidget(
                make_meta_pill(tmdb_ring_items[0], self._profile),
                alignment=Qt.AlignmentFlag.AlignCenter,
            )
            self._tmdb_ring_layout.addStretch(1)
        self._tmdb_ring_slot.setVisible(has_tmdb_ring)

        has_final_stars = star_item is not None
        if has_final_stars:
            self._rating_stars_widget.set_stars(star_item.get("stars"), star_item.get("tooltip") or "")
        else:
            self._rating_stars_widget.set_stars(None)
        self._final_score_stars_block.setVisible(has_final_stars)
        self._final_score_stars_lane.setVisible(has_final_stars)
        self._score_summary_widget.setVisible(self._score_summary_should_show(has_tmdb_ring, has_final_stars))

    def _set_user_score_badge(self, badge: dict | None) -> None:
        if badge is None:
            self._user_score_badge.setText("")
            self._user_score_badge.hide()
            return
        self._user_score_badge.setText(str(badge.get("text", "")))
        self._resize_user_score_badge()
        self._user_score_badge.show()
        self._user_score_badge.raise_()

    def _resize_user_score_badge(self) -> None:
        badge_width = max(
            self._profile.detail_user_score_badge_min_width,
            self._user_score_badge.sizeHint().width(),
        )
        self._user_score_badge.setFixedSize(
            badge_width,
            self._profile.detail_user_score_badge_height,
        )

    def _set_info_grid_items(
        self,
        grid,
        section,
        items: list[dict[str, Any]],
        *,
        label_object_name: str,
        value_object_name: str,
    ) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QLabel, QSizePolicy

        clear_layout(grid)
        compact_row_height = min(
            self._profile.detail_main_info_row_height,
            self._profile.detail_main_info_compact_row_height,
        )
        for row, item in enumerate(items):
            label = QLabel(str(item.get("label", "")))
            label.setObjectName(label_object_name)
            label.setFixedWidth(self._profile.detail_main_info_label_width)
            label.setFixedHeight(compact_row_height)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            value_text = str(item.get("value", ""))
            value = QLabel(value_text)
            value.setObjectName(value_object_name)
            value.setWordWrap(False)
            value.setFixedHeight(compact_row_height)
            value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            value.setToolTip(str(item.get("tooltip") or value_text))

            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)

        section.setVisible(len(items) > 0)

    def _set_main_info_items(self, items: list[dict[str, Any]]) -> None:
        self._main_info_items = list(items)
        self._render_main_info_items()

    def _visible_main_info_items(self) -> list[dict[str, Any]]:
        if self._main_info_expanded:
            return list(self._main_info_items)
        return list(self._main_info_items[:MAIN_INFO_COLLAPSED_ROW_COUNT])

    def _toggle_main_info_expanded(self) -> None:
        self._main_info_expanded = not self._main_info_expanded
        self._render_main_info_items()

    def _update_main_info_toggle_button(self) -> None:
        has_hidden_rows = len(self._main_info_items) > MAIN_INFO_COLLAPSED_ROW_COUNT
        self._main_info_toggle_button.setVisible(has_hidden_rows)
        if has_hidden_rows:
            self._main_info_toggle_button.setText("Скрыть" if self._main_info_expanded else "Показать больше")

    def _render_main_info_items(self) -> None:
        if len(self._main_info_items) <= MAIN_INFO_COLLAPSED_ROW_COUNT:
            self._main_info_expanded = False
        visible_items = self._visible_main_info_items()
        self._set_info_grid_items(
            self._main_info_grid,
            self._main_info_section,
            visible_items,
            label_object_name="detailMainInfoLabel",
            value_object_name="detailMainInfoValue",
        )
        self._update_main_info_toggle_button()
