"""Widget tree builder for DetailCard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from desktop.i18n import tr
from desktop.shared.detail.action_icons import make_detail_action_icon
from desktop.shared.detail.profiles import (
    DetailCardLayoutProfile,
    use_compact_detail_content,
    use_stacked_detail_layout,
)
from desktop.shared.detail.rating_indicator import StarRatingIndicator
from desktop.theme import (
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    COLOR_USER_RATING_HEART,
    FILM_MOVIE_BADGE_BG,
    FILM_MOVIE_BADGE_BORDER,
    FILM_SERIES_BADGE_BG,
    FILM_SERIES_BADGE_BORDER,
    FILM_WINDOW_BG,
    TRANSPARENT_STYLE,
    build_detail_card_style,
    build_poster_placeholder_style,
)

RATING_META_PILLS_SPACING = 1
UNCONSTRAINED_MINIMUM_WIDTH = 0


@dataclass(frozen=True)
class DetailCardHandles:
    """Stable widget handles returned by the DetailCard layout builder."""

    frame: Any
    content_container: Any
    content_center_row: Any
    top_row_widget: Any
    poster_shell: Any
    poster_label: Any
    poster_overlay: Any
    user_score_badge: Any
    media_type_badge: Any
    poster_column_widget: Any
    poster_actions_widget: Any
    poster_actions_layout: Any
    mark_watched_button: Any | None
    hide_button: Any | None
    info_column_widget: Any
    title_block_widget: Any
    title_row_widget: Any
    title_label: Any
    title_meta_label: Any
    score_summary_widget: Any
    score_summary_content: Any
    score_summary_row: Any
    score_summary_top_divider: Any
    score_summary_bottom_divider: Any
    tmdb_ring_slot: Any
    tmdb_ring_layout: Any
    final_score_stars_block: Any
    final_score_stars_label: Any
    final_score_stars_layout: Any
    rating_stars_widget: Any
    final_score_stars_lane: Any
    final_score_stars_lane_layout: Any
    genre_section: Any
    genre_pills_layout: Any
    main_info_section: Any
    main_info_header_widget: Any
    main_info_divider: Any
    main_info_title_label: Any
    main_info_toggle_button: Any
    main_info_panel: Any
    main_info_grid: Any
    overview_frame: Any
    overview_divider: Any
    overview_title_label: Any
    overview_label: Any
    overview_gap_widget: Any


def build_detail_card_layout(owner: Any, parent, profile: DetailCardLayoutProfile) -> DetailCardHandles:
    """Build the DetailCard widget tree and return stable handles."""
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

    card = owner

    class DetailCardFrame(QFrame):
        def resizeEvent(self, event) -> None:
            super().resizeEvent(event)
            card._schedule_poster_height_sync()
            card._schedule_detail_chip_reflow()

    class UserScoreBadgeLabel(QLabel):
        def paintEvent(self, event) -> None:
            from PyQt6.QtCore import QPointF, QRectF, Qt
            from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF

            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            radius = rect.height() / 2
            if self.property("mediaType") == "movie":
                border_color = FILM_MOVIE_BADGE_BORDER
                fill_color = FILM_MOVIE_BADGE_BG
            else:
                border_color = FILM_SERIES_BADGE_BORDER
                fill_color = FILM_SERIES_BADGE_BG
            painter.setPen(QPen(QColor(border_color), 1))
            painter.setBrush(QColor(fill_color))
            painter.drawRoundedRect(rect, radius, radius)
            if self.property("heartBadge"):
                heart_size = min(rect.height() * 0.42, 15.0)
                heart_left = rect.left() + max(7.0, rect.height() * 0.24)
                heart_top = rect.center().y() - (heart_size * 0.52)
                lobe = heart_size * 0.5
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(COLOR_USER_RATING_HEART))
                painter.drawEllipse(QRectF(heart_left, heart_top, lobe, lobe))
                painter.drawEllipse(QRectF(heart_left + lobe, heart_top, lobe, lobe))
                painter.drawPolygon(
                    QPolygonF(
                        [
                            QPointF(heart_left, heart_top + (lobe * 0.46)),
                            QPointF(heart_left + heart_size, heart_top + (lobe * 0.46)),
                            QPointF(heart_left + (heart_size * 0.5), heart_top + heart_size),
                        ]
                    )
                )
                number_rect = rect.adjusted(heart_size + max(8.0, rect.height() * 0.3), 0, -7.0, 0)
                number_font = QFont(painter.font())
                number_font.setBold(True)
                painter.setFont(number_font)
                painter.setPen(QColor(COLOR_TEXT))
                painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, self.text())
            painter.end()
            if self.property("heartBadge") is not True:
                super().paintEvent(event)

    class MediaTypeBadgeLabel(QLabel):
        def paintEvent(self, event) -> None:
            from PyQt6.QtCore import QRectF
            from PyQt6.QtGui import QColor, QPainter, QPen

            if self.property("mediaType") == "tv":
                border_color = FILM_SERIES_BADGE_BORDER
                fill_color = FILM_SERIES_BADGE_BG
            else:
                border_color = FILM_MOVIE_BADGE_BORDER
                fill_color = FILM_WINDOW_BG
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            radius = rect.height() / 2
            painter.setPen(QPen(QColor(border_color), 1))
            painter.setBrush(QColor(fill_color))
            painter.drawRoundedRect(rect, radius, radius)
            painter.end()
            super().paintEvent(event)

    owner._frame = DetailCardFrame(parent)
    owner._frame.setObjectName("detailHeroCard")
    owner._frame.setStyleSheet(build_detail_card_style())
    owner._frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    root = QVBoxLayout(owner._frame)
    root.setContentsMargins(
        profile.detail_hero_card_padding,
        profile.detail_hero_card_padding_top,
        profile.detail_hero_card_padding,
        profile.detail_hero_card_padding,
    )
    root.setSpacing(0)

    owner._content_container = QWidget()
    owner._content_container.setObjectName("detailContentContainer")
    owner._content_container.setStyleSheet(TRANSPARENT_STYLE)
    owner._content_container.setMaximumWidth(profile.detail_content_max_width)
    owner._content_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    content_layout = QVBoxLayout(owner._content_container)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(0)

    owner._top_row_widget = QWidget()
    owner._top_row_widget.setObjectName("detailTopRow")
    owner._top_row_widget.setStyleSheet(TRANSPARENT_STYLE)
    owner._top_row_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    compact_detail_content = use_compact_detail_content() and profile.include_bottom_stretch
    stacked_top_row = use_stacked_detail_layout() and profile.include_bottom_stretch
    top_row_layout_class = QVBoxLayout if stacked_top_row else QHBoxLayout
    top_row = top_row_layout_class(owner._top_row_widget)
    top_row.setContentsMargins(0, 0, 0, 0)
    top_row.setSpacing(profile.detail_poster_right_gap)

    owner._poster_shell = QFrame()
    owner._poster_shell.setObjectName("detailPosterShell")
    owner._poster_shell.setFixedSize(profile.detail_poster_width, profile.detail_poster_height)
    owner._poster_shell.setFrameShape(QFrame.Shape.NoFrame)
    owner._poster_shell.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    poster_shell_layout = QGridLayout(owner._poster_shell)
    poster_border_width = profile.detail_poster_border_width
    poster_shell_layout.setContentsMargins(
        poster_border_width,
        poster_border_width,
        poster_border_width,
        poster_border_width,
    )
    poster_shell_layout.setSpacing(0)

    owner._poster_label = QLabel(tr("detail.poster.none"), owner._poster_shell)
    owner._poster_label.setObjectName("detailPoster")
    owner._poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    owner._poster_label.setFixedSize(
        profile.detail_poster_content_width,
        profile.detail_poster_content_height,
    )
    owner._poster_label.setScaledContents(False)
    owner._poster_label.setStyleSheet(build_poster_placeholder_style())
    owner._poster_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    owner._poster_label.customContextMenuRequested.connect(owner._show_poster_context_menu)

    owner._poster_overlay = QWidget(owner._poster_shell)
    owner._poster_overlay.setObjectName("detailPosterOverlay")
    owner._poster_overlay.setStyleSheet(TRANSPARENT_STYLE)
    owner._poster_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    owner._poster_overlay.setFixedSize(
        profile.detail_poster_content_width,
        profile.detail_poster_content_height,
    )
    poster_overlay_layout = QVBoxLayout(owner._poster_overlay)
    poster_overlay_layout.setContentsMargins(
        max(0, profile.detail_user_score_badge_left - poster_border_width),
        max(0, profile.detail_user_score_badge_top - poster_border_width),
        max(0, profile.detail_user_score_badge_left - poster_border_width),
        max(0, profile.detail_user_score_badge_top - poster_border_width),
    )
    poster_overlay_layout.setSpacing(0)
    poster_score_row = QHBoxLayout()
    poster_score_row.setContentsMargins(0, 0, 0, 0)
    poster_score_row.setSpacing(0)
    poster_badge_row = QHBoxLayout()
    poster_badge_row.setContentsMargins(0, 0, 0, 0)
    poster_badge_row.setSpacing(0)

    owner._user_score_badge = UserScoreBadgeLabel("", owner._poster_shell)
    owner._user_score_badge.setObjectName("detailUserScoreBadge")
    owner._user_score_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    owner._user_score_badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    owner._user_score_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    owner._user_score_badge.setAutoFillBackground(True)
    owner._user_score_badge.setMinimumWidth(profile.detail_user_score_badge_min_width)
    owner._user_score_badge.setFixedHeight(profile.detail_user_score_badge_height)
    owner._user_score_badge.setContentsMargins(
        profile.detail_user_score_badge_padding_x,
        0,
        profile.detail_user_score_badge_padding_x,
        0,
    )
    owner._user_score_badge.hide()

    owner._media_type_badge = MediaTypeBadgeLabel("", owner._poster_shell)
    owner._media_type_badge.setObjectName("detailMediaTypeBadge")
    owner._media_type_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    owner._media_type_badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    owner._media_type_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    owner._media_type_badge.setAutoFillBackground(True)
    owner._media_type_badge.hide()

    poster_shell_layout.addWidget(owner._poster_label, 0, 0)
    poster_score_row.addWidget(
        owner._user_score_badge,
        alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
    )
    poster_score_row.addStretch(1)
    poster_badge_row.addStretch(1)
    poster_badge_row.addWidget(
        owner._media_type_badge,
        alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
    )
    poster_badge_row.addStretch(1)
    poster_overlay_layout.addLayout(poster_score_row)
    poster_overlay_layout.addStretch(1)
    poster_overlay_layout.addLayout(poster_badge_row)
    poster_shell_layout.addWidget(owner._poster_overlay, 0, 0)

    owner._poster_column_widget = QWidget()
    owner._poster_column_widget.setObjectName("detailPosterColumn")
    owner._poster_column_widget.setStyleSheet(TRANSPARENT_STYLE)
    owner._poster_column_widget.setFixedWidth(profile.detail_poster_width)
    owner._poster_column_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
    poster_column = QVBoxLayout(owner._poster_column_widget)
    poster_column.setContentsMargins(0, 0, 0, 0)
    poster_column.setSpacing(profile.detail_poster_actions_top_gap)

    poster_primary_widget = QWidget()
    poster_primary_widget.setObjectName("detailPosterPrimary")
    poster_primary_widget.setStyleSheet(TRANSPARENT_STYLE)
    poster_primary_widget.setFixedWidth(profile.detail_poster_width)
    poster_primary_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    poster_primary_layout = QVBoxLayout(poster_primary_widget)
    poster_primary_layout.setContentsMargins(0, 0, 0, 0)
    poster_primary_layout.setSpacing(profile.detail_poster_actions_top_gap)
    poster_primary_layout.addWidget(owner._poster_shell, alignment=Qt.AlignmentFlag.AlignTop)
    poster_column.addWidget(poster_primary_widget, alignment=Qt.AlignmentFlag.AlignTop)

    owner._info_column_widget = QWidget()
    owner._info_column_widget.setObjectName("detailInfoColumn")
    owner._info_column_widget.setStyleSheet(TRANSPARENT_STYLE)
    owner._info_column_widget.setMinimumWidth(0 if stacked_top_row else profile.detail_info_min_width)
    owner._info_column_widget.setMaximumWidth(profile.detail_info_column_max_width)
    owner._info_column_widget.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Minimum,
    )
    info_column = QVBoxLayout(owner._info_column_widget)
    info_column.setContentsMargins(0, profile.detail_info_top_offset, 0, 0)
    info_column.setSpacing(profile.detail_column_spacing)

    owner._title_block_widget = QWidget()
    owner._title_block_widget.setObjectName("detailTitleBlock")
    owner._title_block_widget.setStyleSheet(TRANSPARENT_STYLE)
    title_block_layout = QVBoxLayout(owner._title_block_widget)
    title_block_layout.setContentsMargins(0, 0, 0, 0)
    title_block_layout.setSpacing(profile.detail_title_meta_gap)

    owner._title_row_widget = QWidget()
    owner._title_row_widget.setStyleSheet(TRANSPARENT_STYLE)
    title_row = QHBoxLayout(owner._title_row_widget)
    title_row.setContentsMargins(0, 0, 0, 0)
    title_row.setSpacing(profile.detail_small_spacing)

    owner._poster_actions_widget = QWidget()
    owner._poster_actions_widget.setObjectName("detailPosterActions")
    owner._poster_actions_widget.setStyleSheet(TRANSPARENT_STYLE)
    owner._poster_actions_layout = QHBoxLayout(owner._poster_actions_widget)
    owner._poster_actions_layout.setContentsMargins(0, 0, 0, 0)
    owner._poster_actions_layout.setSpacing(profile.detail_small_spacing)

    owner._title_label = QLabel(tr("watched.empty.select_title"))
    owner._title_label.setObjectName("detailTitle")
    owner._title_label.setWordWrap(True)
    owner._title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    owner._title_label.setMinimumHeight(profile.detail_title_min_height)
    owner._title_label.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Minimum,
    )

    owner._title_meta_label = QLabel("")
    owner._title_meta_label.setObjectName("detailTitleMeta")
    owner._title_meta_label.setWordWrap(True)
    owner._title_meta_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    owner._title_meta_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    owner._title_meta_label.hide()

    title_block_layout.addWidget(owner._title_row_widget)
    title_block_layout.addWidget(owner._title_meta_label)

    score_summary_widget = QWidget()
    score_summary_widget.setObjectName("detailScoreSummaryRow")
    score_summary_widget.setStyleSheet(TRANSPARENT_STYLE)
    owner._score_summary_widget = score_summary_widget
    score_summary_layout = QVBoxLayout(score_summary_widget)
    score_summary_layout.setContentsMargins(0, 0, 0, 0)
    score_summary_layout.setSpacing(0)

    owner._score_summary_top_divider = QFrame()
    owner._score_summary_top_divider.setObjectName("detailScoreSummaryTopDivider")
    owner._score_summary_top_divider.setFrameShape(QFrame.Shape.HLine)
    owner._score_summary_top_divider.setFixedHeight(profile.detail_divider_height)
    owner._score_summary_top_divider.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )

    owner._score_summary_content = QWidget()
    owner._score_summary_content.setObjectName("detailScoreSummaryContent")
    owner._score_summary_content.setStyleSheet(TRANSPARENT_STYLE)
    score_row_layout_class = QVBoxLayout if compact_detail_content else QHBoxLayout
    owner._score_summary_row = score_row_layout_class(owner._score_summary_content)
    owner._score_summary_row.setContentsMargins(0, 0, 0, 0)
    owner._score_summary_row.setSpacing(profile.detail_stars_left_gap)

    owner._score_summary_bottom_divider = QFrame()
    owner._score_summary_bottom_divider.setObjectName("detailScoreSummaryBottomDivider")
    owner._score_summary_bottom_divider.setFrameShape(QFrame.Shape.HLine)
    owner._score_summary_bottom_divider.setFixedHeight(profile.detail_divider_height)
    owner._score_summary_bottom_divider.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )

    score_summary_layout.addWidget(owner._score_summary_top_divider)
    score_summary_layout.addWidget(owner._score_summary_content)
    score_summary_layout.addWidget(owner._score_summary_bottom_divider)
    score_summary_widget.setMaximumWidth(profile.detail_section_max_width)

    owner._score_indicator = None

    owner._tmdb_ring_slot = QWidget()
    owner._tmdb_ring_slot.setObjectName("detailTmdbRingSlot")
    owner._tmdb_ring_slot.setStyleSheet(TRANSPARENT_STYLE)
    owner._tmdb_ring_slot.setFixedSize(
        profile.detail_rating_widget_size,
        profile.detail_rating_widget_size,
    )
    owner._tmdb_ring_slot.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
    owner._tmdb_ring_layout = QHBoxLayout(owner._tmdb_ring_slot)
    owner._tmdb_ring_layout.setContentsMargins(0, 0, 0, 0)
    owner._tmdb_ring_layout.setSpacing(RATING_META_PILLS_SPACING)

    final_stars_width = 5 * profile.detail_star_size + 4 * profile.detail_star_gap
    owner._final_score_stars_block = QWidget()
    owner._final_score_stars_block.setObjectName("detailFinalScoreStars")
    owner._final_score_stars_block.setStyleSheet(TRANSPARENT_STYLE)
    owner._final_score_stars_block.setMinimumWidth(final_stars_width)
    owner._final_score_stars_block.setMinimumHeight(
        profile.detail_star_size + (2 * profile.detail_small_spacing)
    )
    owner._final_score_stars_block.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    owner._final_score_stars_layout = QVBoxLayout(owner._final_score_stars_block)
    owner._final_score_stars_layout.setContentsMargins(0, 0, 0, 0)
    owner._final_score_stars_layout.setSpacing(profile.detail_small_spacing)

    owner._final_score_stars_label = QLabel("WatchBane")
    owner._final_score_stars_label.setObjectName("detailFinalScoreStarsLabel")
    owner._final_score_stars_label.setWordWrap(True)
    owner._final_score_stars_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
    owner._final_score_stars_label.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Minimum,
    )
    owner._final_score_stars_layout.addWidget(owner._final_score_stars_label)

    owner._rating_stars_widget = StarRatingIndicator(
        star_size=profile.detail_star_size,
        star_gap=profile.detail_star_gap,
    )
    owner._rating_stars_widget.setObjectName("detailFinalScoreStarsWidget")
    owner._final_score_stars_layout.addWidget(
        owner._rating_stars_widget,
        alignment=Qt.AlignmentFlag.AlignLeft,
    )

    owner._final_score_stars_lane = QWidget()
    owner._final_score_stars_lane.setObjectName("detailFinalScoreStarsLane")
    owner._final_score_stars_lane.setStyleSheet(TRANSPARENT_STYLE)
    owner._final_score_stars_lane.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Minimum,
    )
    owner._final_score_stars_lane_layout = QHBoxLayout(owner._final_score_stars_lane)
    owner._final_score_stars_lane_layout.setContentsMargins(0, 0, 0, 0)
    owner._final_score_stars_lane_layout.setSpacing(0)
    owner._final_score_stars_lane_layout.addWidget(
        owner._final_score_stars_block,
        alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )
    owner._final_score_stars_lane_layout.addStretch(1)

    if compact_detail_content:
        owner._score_summary_row.addWidget(
            owner._tmdb_ring_slot,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        owner._score_summary_row.addWidget(
            owner._final_score_stars_lane,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
    else:
        owner._score_summary_row.addWidget(
            owner._tmdb_ring_slot,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        owner._score_summary_row.addWidget(
            owner._final_score_stars_lane,
            stretch=1,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
    if profile.show_mark_watched_button:
        mark_watched_button = QPushButton()
        owner._mark_watched_button = mark_watched_button
        owner._mark_watched_button.setObjectName("candidateMarkWatchedButton")
        owner._mark_watched_button.setToolTip(tr("detail.action.mark_watched"))
        owner._mark_watched_button.setIcon(
            make_detail_action_icon("eye", COLOR_TEXT, COLOR_TEXT_SECONDARY)
        )
        owner._mark_watched_button.setIconSize(
            QSize(
                profile.detail_candidate_action_icon_size,
                profile.detail_candidate_action_icon_size,
            )
        )
        owner._mark_watched_button.setFixedSize(
            profile.detail_candidate_action_button_size,
            profile.detail_candidate_action_button_size,
        )
        owner._mark_watched_button.setEnabled(False)
        owner._mark_watched_button.clicked.connect(owner._on_mark_watched_clicked)
        owner._poster_actions_layout.addWidget(
            owner._mark_watched_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
    if profile.show_hide_candidate_button:
        hide_button = QPushButton()
        owner._hide_button = hide_button
        owner._hide_button.setObjectName("candidateHideButton")
        owner._hide_button.setToolTip(tr("detail.action.hide_candidate"))
        owner._hide_button.setIcon(
            make_detail_action_icon("hide", COLOR_TEXT, COLOR_TEXT_SECONDARY)
        )
        owner._hide_button.setIconSize(
            QSize(
                profile.detail_candidate_action_icon_size,
                profile.detail_candidate_action_icon_size,
            )
        )
        owner._hide_button.setFixedSize(
            profile.detail_candidate_action_button_size,
            profile.detail_candidate_action_button_size,
        )
        owner._hide_button.setEnabled(False)
        owner._hide_button.clicked.connect(owner._on_hide_clicked)
        owner._poster_actions_layout.addWidget(
            owner._hide_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
    owner._poster_actions_layout.addStretch(1)
    show_poster_actions = profile.show_mark_watched_button or profile.show_hide_candidate_button
    owner._poster_actions_widget.setVisible(show_poster_actions)
    title_row.addWidget(owner._title_label, stretch=1)
    poster_primary_layout.addWidget(owner._poster_actions_widget)
    poster_primary_height = profile.detail_poster_height
    if show_poster_actions:
        owner._poster_actions_widget.setFixedHeight(profile.detail_candidate_action_button_size)
        poster_primary_height += profile.detail_poster_actions_top_gap + profile.detail_candidate_action_button_size
    poster_primary_widget.setFixedHeight(poster_primary_height)

    owner._genre_section = QWidget()
    owner._genre_section.setObjectName("detailChipsContainer")
    owner._genre_section.setStyleSheet(TRANSPARENT_STYLE)
    owner._genre_pills_layout = QVBoxLayout(owner._genre_section)
    owner._genre_pills_layout.setContentsMargins(0, 0, 0, 0)
    owner._genre_pills_layout.setSpacing(profile.detail_chip_row_gap)

    owner._main_info_section = QWidget()
    owner._main_info_section.setObjectName("detailMainInfoSection")
    owner._main_info_section.setStyleSheet(TRANSPARENT_STYLE)
    owner._main_info_section.setMaximumWidth(profile.detail_section_max_width)
    owner._main_info_section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    main_info_layout = QVBoxLayout(owner._main_info_section)
    main_info_layout.setContentsMargins(0, 0, 0, 0)
    main_info_layout.setSpacing(profile.detail_main_info_header_panel_gap)

    owner._main_info_header_widget = QWidget()
    owner._main_info_header_widget.setStyleSheet(TRANSPARENT_STYLE)
    main_info_header_layout = QVBoxLayout(owner._main_info_header_widget)
    main_info_header_layout.setContentsMargins(0, 0, 0, 0)
    main_info_header_layout.setSpacing(profile.detail_small_spacing)
    main_info_button_row = QHBoxLayout()
    main_info_button_row.setContentsMargins(0, 0, 0, 0)
    main_info_button_row.setSpacing(profile.detail_column_spacing)

    owner._main_info_divider = QFrame()
    owner._main_info_divider.setObjectName("detailMainInfoHeaderDivider")
    owner._main_info_divider.setFrameShape(QFrame.Shape.HLine)
    owner._main_info_divider.setFixedHeight(profile.detail_divider_height)
    owner._main_info_divider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    owner._main_info_title_label = QLabel(tr("detail.main_info.title"))
    owner._main_info_title_label.setObjectName("detailMainInfoHeader")
    owner._main_info_title_label.setWordWrap(True)
    owner._main_info_title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    owner._main_info_toggle_button = QPushButton(tr("detail.show_more"))
    owner._main_info_toggle_button.setObjectName("detailMainInfoToggleButton")
    owner._main_info_toggle_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    toggle_text_width = max(
        owner._main_info_toggle_button.fontMetrics().horizontalAdvance(tr("detail.show_more")),
        owner._main_info_toggle_button.fontMetrics().horizontalAdvance(tr("detail.show_less")),
    )
    owner._main_info_toggle_button.setMinimumWidth(
        toggle_text_width + (4 * profile.detail_small_spacing)
    )
    owner._main_info_toggle_button.setAutoDefault(False)
    owner._main_info_toggle_button.setDefault(False)
    owner._main_info_toggle_button.clicked.connect(owner._toggle_main_info_expanded)
    owner._main_info_toggle_button.hide()

    main_info_header_layout.addWidget(owner._main_info_title_label)
    main_info_button_row.addWidget(owner._main_info_toggle_button)
    main_info_button_row.addWidget(owner._main_info_divider, stretch=1)
    main_info_header_layout.addLayout(main_info_button_row)

    owner._main_info_panel = QFrame()
    owner._main_info_panel.setObjectName("detailMainInfoPanel")
    owner._main_info_panel.setFrameShape(QFrame.Shape.NoFrame)
    owner._main_info_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    owner._main_info_grid = QGridLayout(owner._main_info_panel)
    main_info_padding_y = min(
        profile.detail_main_info_panel_padding_y,
        profile.detail_main_info_compact_padding_y_cap,
    )
    owner._main_info_grid.setContentsMargins(
        profile.detail_main_info_panel_padding_x,
        main_info_padding_y,
        profile.detail_main_info_panel_padding_x,
        main_info_padding_y,
    )
    owner._main_info_grid.setHorizontalSpacing(profile.detail_chip_col_gap)
    owner._main_info_grid.setVerticalSpacing(profile.detail_main_info_row_gap)
    owner._main_info_grid.setColumnStretch(0, 0)
    owner._main_info_grid.setColumnStretch(1, 1)

    main_info_layout.addWidget(owner._main_info_header_widget)
    main_info_layout.addWidget(owner._main_info_panel)

    owner._overview_frame = QFrame()
    owner._overview_frame.setObjectName("detailOverviewSection")
    owner._overview_frame.setFrameShape(QFrame.Shape.NoFrame)
    if stacked_top_row:
        owner._overview_frame.setMinimumWidth(UNCONSTRAINED_MINIMUM_WIDTH)
        owner._overview_frame.setMaximumWidth(profile.detail_section_max_width)
        owner._overview_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    else:
        owner._overview_frame.setFixedWidth(profile.detail_poster_width)
        owner._overview_frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
    overview_layout = QVBoxLayout(owner._overview_frame)
    overview_layout.setContentsMargins(profile.detail_overview_left_inset, 0, 0, 0)
    overview_layout.setSpacing(0)

    owner._overview_divider = QFrame()
    owner._overview_divider.setObjectName("detailOverviewDivider")
    owner._overview_divider.setFrameShape(QFrame.Shape.HLine)
    owner._overview_divider.setFixedHeight(profile.detail_divider_height)
    owner._overview_divider.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    owner._overview_title_label = QLabel(tr("detail.overview.title"))
    owner._overview_title_label.setObjectName("detailOverviewHeader")
    owner._overview_title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    owner._overview_label = QLabel("")
    owner._overview_label.setObjectName("detailOverviewText")
    owner._overview_label.setWordWrap(True)
    owner._overview_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    owner._overview_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    overview_layout.addWidget(owner._overview_divider)
    overview_layout.addSpacing(profile.detail_overview_title_top_gap)
    overview_layout.addWidget(owner._overview_title_label)
    overview_layout.addSpacing(profile.detail_overview_text_top_gap)
    overview_layout.addWidget(owner._overview_label)
    owner._overview_frame.hide()

    owner._overview_gap_widget = QWidget()
    owner._overview_gap_widget.setObjectName("detailOverviewTopGap")
    owner._overview_gap_widget.setStyleSheet(TRANSPARENT_STYLE)
    owner._overview_gap_widget.setFixedHeight(profile.detail_overview_top_gap)
    owner._overview_gap_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    owner._overview_gap_widget.hide()
    if not stacked_top_row:
        poster_column.addWidget(owner._overview_gap_widget)
        poster_column.addWidget(owner._overview_frame, alignment=Qt.AlignmentFlag.AlignLeft)
    poster_column.addStretch(1)

    info_column.addWidget(owner._title_block_widget)
    info_column.addSpacing(profile.detail_title_chips_gap)
    info_column.addWidget(owner._genre_section)
    info_column.addSpacing(profile.detail_micro_spacing)
    info_column.addWidget(score_summary_widget)
    info_column.addSpacing(profile.detail_section_spacing)
    info_column.addWidget(owner._main_info_section)

    poster_alignment = Qt.AlignmentFlag.AlignTop
    if stacked_top_row:
        poster_alignment |= Qt.AlignmentFlag.AlignHCenter
    top_row.addWidget(owner._poster_column_widget, alignment=poster_alignment)
    top_row.addWidget(owner._info_column_widget, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
    if stacked_top_row:
        top_row.addWidget(owner._overview_gap_widget)
        top_row.addWidget(owner._overview_frame)
    content_layout.addWidget(owner._top_row_widget)
    if profile.include_bottom_stretch:
        content_layout.addStretch(1)

    owner._content_center_row = QWidget()
    owner._content_center_row.setObjectName("detailContentCenterRow")
    owner._content_center_row.setStyleSheet(TRANSPARENT_STYLE)
    owner._content_center_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    content_center_layout = QHBoxLayout(owner._content_center_row)
    content_center_layout.setContentsMargins(0, 0, 0, 0)
    content_center_layout.setSpacing(0)
    content_center_layout.addStretch(1)
    content_center_layout.addWidget(owner._content_container, stretch=100)
    content_center_layout.addStretch(1)

    root.addWidget(
        owner._content_center_row,
        alignment=Qt.AlignmentFlag.AlignTop,
    )


    return DetailCardHandles(
        frame=owner._frame,
        content_container=owner._content_container,
        content_center_row=owner._content_center_row,
        top_row_widget=owner._top_row_widget,
        poster_shell=owner._poster_shell,
        poster_label=owner._poster_label,
        poster_overlay=owner._poster_overlay,
        user_score_badge=owner._user_score_badge,
        media_type_badge=owner._media_type_badge,
        poster_column_widget=owner._poster_column_widget,
        poster_actions_widget=owner._poster_actions_widget,
        poster_actions_layout=owner._poster_actions_layout,
        mark_watched_button=owner._mark_watched_button,
        hide_button=owner._hide_button,
        info_column_widget=owner._info_column_widget,
        title_block_widget=owner._title_block_widget,
        title_row_widget=owner._title_row_widget,
        title_label=owner._title_label,
        title_meta_label=owner._title_meta_label,
        score_summary_widget=owner._score_summary_widget,
        score_summary_content=owner._score_summary_content,
        score_summary_row=owner._score_summary_row,
        score_summary_top_divider=owner._score_summary_top_divider,
        score_summary_bottom_divider=owner._score_summary_bottom_divider,
        tmdb_ring_slot=owner._tmdb_ring_slot,
        tmdb_ring_layout=owner._tmdb_ring_layout,
        final_score_stars_block=owner._final_score_stars_block,
        final_score_stars_label=owner._final_score_stars_label,
        final_score_stars_layout=owner._final_score_stars_layout,
        rating_stars_widget=owner._rating_stars_widget,
        final_score_stars_lane=owner._final_score_stars_lane,
        final_score_stars_lane_layout=owner._final_score_stars_lane_layout,
        genre_section=owner._genre_section,
        genre_pills_layout=owner._genre_pills_layout,
        main_info_section=owner._main_info_section,
        main_info_header_widget=owner._main_info_header_widget,
        main_info_divider=owner._main_info_divider,
        main_info_title_label=owner._main_info_title_label,
        main_info_toggle_button=owner._main_info_toggle_button,
        main_info_panel=owner._main_info_panel,
        main_info_grid=owner._main_info_grid,
        overview_frame=owner._overview_frame,
        overview_divider=owner._overview_divider,
        overview_title_label=owner._overview_title_label,
        overview_label=owner._overview_label,
        overview_gap_widget=owner._overview_gap_widget,
    )

