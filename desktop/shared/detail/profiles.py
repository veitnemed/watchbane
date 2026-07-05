"""Layout profiles and sizing constants for detail cards."""

from __future__ import annotations

from dataclasses import dataclass, replace

from desktop.theme import (
    DETAIL_CHIP_COL_GAP,
    DETAIL_CHIP_H_PADDING,
    DETAIL_CHIP_HEIGHT,
    DETAIL_CHIP_MAX_ROWS,
    DETAIL_CHIP_MAX_WIDTH,
    DETAIL_CHIP_RADIUS,
    DETAIL_CHIP_ROW_GAP,
    DETAIL_HERO_CARD_PADDING,
    DETAIL_HERO_CARD_RADIUS,
    DETAIL_HERO_MIN_WIDTH,
    DETAIL_HERO_PREFERRED_MIN_WIDTH,
    DETAIL_INFO_MAX_WIDTH,
    DETAIL_INFO_MIN_WIDTH,
    DETAIL_MAIN_INFO_LABEL_WIDTH,
    DETAIL_MAIN_INFO_PANEL_PADDING_X,
    DETAIL_MAIN_INFO_PANEL_PADDING_Y,
    DETAIL_MAIN_INFO_PANEL_RADIUS,
    DETAIL_MAIN_INFO_ROW_HEIGHT,
    DETAIL_MAIN_INFO_TOP_GAP,
    DETAIL_OVERVIEW_LEFT_INSET,
    DETAIL_OVERVIEW_MAX_LINES_COLLAPSED,
    DETAIL_OVERVIEW_TEXT_TOP_GAP,
    DETAIL_OVERVIEW_TITLE_TOP_GAP,
    DETAIL_OVERVIEW_TOP_GAP,
    DETAIL_POSTER_HEIGHT,
    DETAIL_POSTER_RADIUS,
    DETAIL_POSTER_RIGHT_GAP,
    DETAIL_POSTER_WIDTH,
    DETAIL_RATING_CIRCLE_DIAMETER,
    DETAIL_RATING_WIDGET_SIZE,
    DETAIL_SCORE_ROW_TOP_GAP,
    DETAIL_STAR_GAP,
    DETAIL_STAR_SIZE,
    DETAIL_STARS_LEFT_GAP,
    DETAIL_TITLE_FONT_FALLBACK,
    DETAIL_TITLE_FONT_FAMILY,
    DETAIL_TITLE_FONT_SIZE,
    DETAIL_TITLE_LINE_HEIGHT,
    DETAIL_TITLE_MAX_LINES,
    DETAIL_USER_SCORE_BADGE_HEIGHT,
    DETAIL_USER_SCORE_BADGE_MIN_WIDTH,
    DETAIL_USER_SCORE_BADGE_PADDING_X,
    DETAIL_USER_SCORE_BADGE_RADIUS,
    DETAIL_USER_SCORE_BADGE_RIGHT,
    DETAIL_USER_SCORE_BADGE_TOP,
    FONT_RATING_LABEL_POINT,
    FONT_RATING_VALUE_POINT,
    build_detail_card_style,
    build_poster_image_style,
    build_poster_placeholder_style,
)

POSTER_BASE_WIDTH = 220
POSTER_BASE_HEIGHT = 330
POSTER_DISPLAY_SCALE = 1.25
POSTER_WIDTH = int(POSTER_BASE_WIDTH * POSTER_DISPLAY_SCALE)
POSTER_HEIGHT = int(POSTER_BASE_HEIGHT * POSTER_DISPLAY_SCALE)
POSTER_TOP_ROW_SPACING = int(22 * POSTER_DISPLAY_SCALE)
LIST_ITEM_HEIGHT = 72
LIST_THUMB_WIDTH = 40
LIST_THUMB_HEIGHT = 60
LIST_ITEM_H_PADDING = 10
LIST_ITEM_V_PADDING = 6
LIST_TEXT_GAP = 10
GENRES_PER_ROW = 4
CARD_PADDING = 22
RATING_CIRCLE_WIDGET_SIZE = 88
RATING_CIRCLE_DIAMETER = 78

POSTER_PLACEHOLDER_STYLE = build_poster_placeholder_style()
POSTER_IMAGE_STYLE = build_poster_image_style()
DETAIL_CARD_STYLE = build_detail_card_style()


@dataclass(frozen=True)
class DetailCardLayoutProfile:
    """Layout sizing for WatchedDetailCard (full watched view vs compact add-preview)."""

    poster_width: int
    poster_height: int
    poster_row_spacing: int
    card_padding: int
    rating_widget_size: int
    rating_circle_diameter: int
    rating_value_font_point: int
    rating_label_font_point: int
    show_user_score: bool = True
    show_mark_watched_button: bool = False
    show_hide_candidate_button: bool = False
    include_bottom_stretch: bool = True
    detail_hero_card_radius: int = DETAIL_HERO_CARD_RADIUS
    detail_hero_card_padding: int = DETAIL_HERO_CARD_PADDING
    detail_hero_min_width: int = DETAIL_HERO_MIN_WIDTH
    detail_hero_preferred_min_width: int = DETAIL_HERO_PREFERRED_MIN_WIDTH
    detail_poster_width: int = DETAIL_POSTER_WIDTH
    detail_poster_height: int = DETAIL_POSTER_HEIGHT
    detail_poster_radius: int = DETAIL_POSTER_RADIUS
    detail_poster_right_gap: int = DETAIL_POSTER_RIGHT_GAP
    detail_info_min_width: int = DETAIL_INFO_MIN_WIDTH
    detail_info_max_width: int = DETAIL_INFO_MAX_WIDTH
    detail_title_font_family: str = DETAIL_TITLE_FONT_FAMILY
    detail_title_font_fallback: str = DETAIL_TITLE_FONT_FALLBACK
    detail_title_font_size: int = DETAIL_TITLE_FONT_SIZE
    detail_title_line_height: int = DETAIL_TITLE_LINE_HEIGHT
    detail_title_max_lines: int = DETAIL_TITLE_MAX_LINES
    detail_chip_height: int = DETAIL_CHIP_HEIGHT
    detail_chip_radius: int = DETAIL_CHIP_RADIUS
    detail_chip_h_padding: int = DETAIL_CHIP_H_PADDING
    detail_chip_row_gap: int = DETAIL_CHIP_ROW_GAP
    detail_chip_col_gap: int = DETAIL_CHIP_COL_GAP
    detail_chip_max_rows: int = DETAIL_CHIP_MAX_ROWS
    detail_chip_max_width: int = DETAIL_CHIP_MAX_WIDTH
    detail_score_row_top_gap: int = DETAIL_SCORE_ROW_TOP_GAP
    detail_rating_widget_size: int = DETAIL_RATING_WIDGET_SIZE
    detail_rating_circle_diameter: int = DETAIL_RATING_CIRCLE_DIAMETER
    detail_stars_left_gap: int = DETAIL_STARS_LEFT_GAP
    detail_star_size: int = DETAIL_STAR_SIZE
    detail_star_gap: int = DETAIL_STAR_GAP
    detail_user_score_badge_min_width: int = DETAIL_USER_SCORE_BADGE_MIN_WIDTH
    detail_user_score_badge_height: int = DETAIL_USER_SCORE_BADGE_HEIGHT
    detail_user_score_badge_radius: int = DETAIL_USER_SCORE_BADGE_RADIUS
    detail_user_score_badge_top: int = DETAIL_USER_SCORE_BADGE_TOP
    detail_user_score_badge_right: int = DETAIL_USER_SCORE_BADGE_RIGHT
    detail_user_score_badge_padding_x: int = DETAIL_USER_SCORE_BADGE_PADDING_X
    detail_main_info_top_gap: int = DETAIL_MAIN_INFO_TOP_GAP
    detail_main_info_panel_radius: int = DETAIL_MAIN_INFO_PANEL_RADIUS
    detail_main_info_panel_padding_x: int = DETAIL_MAIN_INFO_PANEL_PADDING_X
    detail_main_info_panel_padding_y: int = DETAIL_MAIN_INFO_PANEL_PADDING_Y
    detail_main_info_row_height: int = DETAIL_MAIN_INFO_ROW_HEIGHT
    detail_main_info_label_width: int = DETAIL_MAIN_INFO_LABEL_WIDTH
    detail_overview_top_gap: int = DETAIL_OVERVIEW_TOP_GAP
    detail_overview_left_inset: int = DETAIL_OVERVIEW_LEFT_INSET
    detail_overview_title_top_gap: int = DETAIL_OVERVIEW_TITLE_TOP_GAP
    detail_overview_text_top_gap: int = DETAIL_OVERVIEW_TEXT_TOP_GAP
    detail_overview_max_lines_collapsed: int = DETAIL_OVERVIEW_MAX_LINES_COLLAPSED


DETAIL_CARD_LAYOUT_PROFILE = DetailCardLayoutProfile(
    poster_width=POSTER_WIDTH,
    poster_height=POSTER_HEIGHT,
    poster_row_spacing=POSTER_TOP_ROW_SPACING,
    card_padding=CARD_PADDING,
    rating_widget_size=RATING_CIRCLE_WIDGET_SIZE,
    rating_circle_diameter=RATING_CIRCLE_DIAMETER,
    rating_value_font_point=FONT_RATING_VALUE_POINT,
    rating_label_font_point=FONT_RATING_LABEL_POINT,
    show_user_score=True,
)

ADD_TITLE_PREVIEW_CARD_PROFILE = DetailCardLayoutProfile(
    poster_width=POSTER_WIDTH // 2,
    poster_height=POSTER_HEIGHT // 2,
    poster_row_spacing=max(10, POSTER_TOP_ROW_SPACING // 2),
    card_padding=14,
    rating_widget_size=50,
    rating_circle_diameter=44,
    rating_value_font_point=11,
    rating_label_font_point=7,
    show_user_score=False,
    include_bottom_stretch=False,
    detail_poster_width=POSTER_WIDTH // 2,
    detail_poster_height=POSTER_HEIGHT // 2,
)

CANDIDATE_DETAIL_CARD_PROFILE = replace(
    DETAIL_CARD_LAYOUT_PROFILE,
    show_user_score=False,
    show_mark_watched_button=True,
    show_hide_candidate_button=True,
)
