"""Layout profiles and sizing constants for detail cards."""

from __future__ import annotations

from dataclasses import dataclass, replace

from desktop.theme import (
    DETAIL_CHIP_COL_GAP,
    DETAIL_CHIP_FONT_SIZE,
    DETAIL_CHIP_H_PADDING,
    DETAIL_CHIP_HEIGHT,
    DETAIL_CHIP_MAX_ROWS,
    DETAIL_CHIP_MAX_WIDTH,
    DETAIL_CHIP_RADIUS,
    DETAIL_CHIP_ROW_GAP,
    DETAIL_HERO_CARD_PADDING,
    DETAIL_HERO_CARD_PADDING_TOP,
    DETAIL_HERO_CARD_RADIUS,
    DETAIL_CONTENT_MAX_WIDTH,
    DETAIL_HERO_MIN_WIDTH,
    DETAIL_HERO_PREFERRED_MIN_WIDTH,
    DETAIL_INFO_COLUMN_MAX_WIDTH,
    DETAIL_INFO_MAX_WIDTH,
    DETAIL_INFO_MIN_WIDTH,
    DETAIL_INFO_TOP_OFFSET,
    DETAIL_MAIN_INFO_LABEL_WIDTH,
    DETAIL_MAIN_INFO_PANEL_PADDING_X,
    DETAIL_MAIN_INFO_PANEL_PADDING_Y,
    DETAIL_MAIN_INFO_PANEL_RADIUS,
    DETAIL_MAIN_INFO_HEADER_PANEL_GAP,
    DETAIL_MAIN_INFO_ROW_GAP,
    DETAIL_MAIN_INFO_ROW_HEIGHT,
    DETAIL_MAIN_INFO_TOP_GAP,
    DETAIL_OVERVIEW_LEFT_INSET,
    DETAIL_OVERVIEW_MAX_LINES_COLLAPSED,
    DETAIL_OVERVIEW_MAX_WIDTH,
    DETAIL_OVERVIEW_TEXT_TOP_GAP,
    DETAIL_OVERVIEW_TITLE_TOP_GAP,
    DETAIL_OVERVIEW_TOP_GAP,
    DETAIL_POSTER_HEIGHT,
    DETAIL_POSTER_BORDER_WIDTH,
    DETAIL_POSTER_RADIUS,
    DETAIL_POSTER_RIGHT_GAP,
    DETAIL_POSTER_WIDTH,
    DETAIL_RATING_CIRCLE_DIAMETER,
    DETAIL_RATING_WIDGET_SIZE,
    DETAIL_SCORE_ROW_TOP_GAP,
    DETAIL_SECTION_MAX_WIDTH,
    DETAIL_STAR_GAP,
    DETAIL_STAR_SIZE,
    DETAIL_STARS_LEFT_GAP,
    DETAIL_SCORE_MAIN_INFO_GAP,
    DETAIL_TITLE_CHIPS_GAP,
    DETAIL_TITLE_FONT_FALLBACK,
    DETAIL_TITLE_FONT_FAMILY,
    DETAIL_TITLE_FONT_SIZE,
    DETAIL_TITLE_LINE_HEIGHT,
    DETAIL_TITLE_MAX_LINES,
    DETAIL_USER_SCORE_BADGE_HEIGHT,
    DETAIL_USER_SCORE_BADGE_MIN_WIDTH,
    DETAIL_USER_SCORE_BADGE_PADDING_X,
    DETAIL_USER_SCORE_BADGE_RADIUS,
    DETAIL_USER_SCORE_BADGE_LEFT,
    DETAIL_USER_SCORE_BADGE_TOP,
    FONT_RATING_LABEL_POINT,
    FONT_RATING_VALUE_POINT,
    LIST_CARD_CORNER_RADIUS,
    LIST_FALLBACK_WIDTH,
    LIST_ITEM_HEIGHT_BASE,
    LIST_ITEM_H_PADDING_BASE,
    LIST_ITEM_V_PADDING_BASE,
    LIST_META_BAND_HEIGHT,
    LIST_META_FONT_SIZE,
    LIST_MIN_TEXT_WIDTH,
    LIST_PLACEHOLDER_FONT_SIZE,
    LIST_ROW_INSET_X,
    LIST_ROW_INSET_Y,
    LIST_TEXT_GAP_BASE,
    LIST_THUMB_CORNER_RADIUS,
    LIST_THUMB_HEIGHT_BASE,
    LIST_THUMB_WIDTH_BASE,
    LIST_TITLE_BAND_HEIGHT,
    LIST_TITLE_FONT_SIZE,
    build_detail_card_style,
    build_poster_image_style,
    build_poster_placeholder_style,
    detail_px,
    font_px,
    list_px,
    poster_px,
)
from desktop.theme.layout import (
    DETAIL_CHIP_COL_GAP,
    DETAIL_CHIP_FONT_SIZE,
    DETAIL_CHIP_H_PADDING,
    DETAIL_CHIP_HEIGHT,
    DETAIL_CHIP_MAX_ROWS,
    DETAIL_CHIP_MAX_WIDTH,
    DETAIL_CHIP_RADIUS,
    DETAIL_CHIP_ROW_GAP,
    DETAIL_CONTENT_MAX_WIDTH,
    DETAIL_HERO_CARD_PADDING,
    DETAIL_HERO_CARD_PADDING_TOP,
    DETAIL_HERO_CARD_RADIUS,
    DETAIL_HERO_MIN_WIDTH,
    DETAIL_HERO_PREFERRED_MIN_WIDTH,
    DETAIL_INFO_COLUMN_MAX_WIDTH,
    DETAIL_INFO_MAX_WIDTH,
    DETAIL_INFO_MIN_WIDTH,
    DETAIL_INFO_TOP_OFFSET,
    DETAIL_MAIN_INFO_HEADER_PANEL_GAP,
    DETAIL_MAIN_INFO_LABEL_WIDTH,
    DETAIL_MAIN_INFO_PANEL_PADDING_X,
    DETAIL_MAIN_INFO_PANEL_PADDING_Y,
    DETAIL_MAIN_INFO_PANEL_RADIUS,
    DETAIL_MAIN_INFO_ROW_GAP,
    DETAIL_MAIN_INFO_ROW_HEIGHT,
    DETAIL_MAIN_INFO_TOP_GAP,
    DETAIL_OVERVIEW_LEFT_INSET,
    DETAIL_OVERVIEW_MAX_LINES_COLLAPSED,
    DETAIL_OVERVIEW_MAX_WIDTH,
    DETAIL_OVERVIEW_TEXT_TOP_GAP,
    DETAIL_OVERVIEW_TITLE_TOP_GAP,
    DETAIL_OVERVIEW_TOP_GAP,
    DETAIL_POSTER_BORDER_WIDTH,
    DETAIL_POSTER_HEIGHT,
    DETAIL_POSTER_RADIUS,
    DETAIL_POSTER_RIGHT_GAP,
    DETAIL_POSTER_WIDTH,
    DETAIL_RATING_CIRCLE_DIAMETER,
    DETAIL_RATING_WIDGET_SIZE,
    DETAIL_SCORE_MAIN_INFO_GAP,
    DETAIL_SCORE_ROW_TOP_GAP,
    DETAIL_SECTION_MAX_WIDTH,
    DETAIL_STAR_GAP,
    DETAIL_STAR_SIZE,
    DETAIL_STARS_LEFT_GAP,
    DETAIL_TITLE_CHIPS_GAP,
    DETAIL_TITLE_FONT_SIZE,
    DETAIL_TITLE_LINE_HEIGHT,
    DETAIL_TITLE_MAX_LINES,
    DETAIL_USER_SCORE_BADGE_HEIGHT,
    DETAIL_USER_SCORE_BADGE_LEFT,
    DETAIL_USER_SCORE_BADGE_MIN_WIDTH,
    DETAIL_USER_SCORE_BADGE_PADDING_X,
    DETAIL_USER_SCORE_BADGE_RADIUS,
    DETAIL_USER_SCORE_BADGE_TOP,
    LIST_FALLBACK_WIDTH,
    LIST_ITEM_HEIGHT_BASE,
    LIST_ITEM_H_PADDING_BASE,
    LIST_ITEM_V_PADDING_BASE,
    LIST_META_BAND_HEIGHT,
    LIST_MIN_TEXT_WIDTH,
    LIST_ROW_INSET_X,
    LIST_ROW_INSET_Y,
    LIST_TEXT_GAP_BASE,
    LIST_THUMB_HEIGHT_BASE,
    LIST_THUMB_WIDTH_BASE,
    LIST_TITLE_BAND_HEIGHT,
    detail_px,
    font_px,
    list_px,
    poster_px,
)
from desktop.theme.scaling import get_ui_scale

DETAIL_COMPACT_UI_SCALE = 1.10
DETAIL_STACKED_UI_SCALE = 1.25
DETAIL_STACKED_INFO_UI_SCALE = 1.00
DETAIL_COMPACT_POSTER_WIDTH = 300
DETAIL_STACKED_POSTER_WIDTH = 245


def use_compact_detail_content() -> bool:
    """Tighten fixed detail geometry before the two columns need to stack."""
    return get_ui_scale() >= DETAIL_COMPACT_UI_SCALE


def use_stacked_detail_info_rows() -> bool:
    """Keep long metadata labels and values from competing for one line."""
    return get_ui_scale() >= DETAIL_STACKED_INFO_UI_SCALE


def use_stacked_detail_layout() -> bool:
    """Use the narrow-column detail composition once scaled panes stop fitting."""
    return get_ui_scale() >= DETAIL_STACKED_UI_SCALE


def detail_poster_px(value: int | float) -> int:
    """Scale full detail posters without letting high UI scales overflow the viewport."""
    scaled = poster_px(value)
    if not use_compact_detail_content():
        return scaled
    target_width = (
        DETAIL_STACKED_POSTER_WIDTH
        if use_stacked_detail_layout()
        else DETAIL_COMPACT_POSTER_WIDTH
    )
    compact_ratio = target_width / DETAIL_POSTER_WIDTH
    compact_base = float(value) * compact_ratio
    return max(1, int(round(poster_px(compact_base) / get_ui_scale())))


def compact_detail_px(value: int | float, compact_value: int | float) -> int:
    selected = compact_value if use_compact_detail_content() else value
    return detail_px(selected)

POSTER_BASE_WIDTH = 220
POSTER_BASE_HEIGHT = 330
POSTER_DISPLAY_SCALE = 1.25
POSTER_WIDTH = poster_px(int(POSTER_BASE_WIDTH * POSTER_DISPLAY_SCALE))
POSTER_HEIGHT = poster_px(int(POSTER_BASE_HEIGHT * POSTER_DISPLAY_SCALE))
POSTER_TOP_ROW_SPACING = detail_px(int(22 * POSTER_DISPLAY_SCALE))
LIST_ITEM_HEIGHT = list_px(LIST_ITEM_HEIGHT_BASE)
LIST_THUMB_WIDTH = list_px(LIST_THUMB_WIDTH_BASE)
LIST_THUMB_HEIGHT = list_px(LIST_THUMB_HEIGHT_BASE)
LIST_ITEM_H_PADDING = list_px(LIST_ITEM_H_PADDING_BASE)
LIST_ITEM_V_PADDING = list_px(LIST_ITEM_V_PADDING_BASE)
LIST_TEXT_GAP = list_px(LIST_TEXT_GAP_BASE)
LIST_FALLBACK_WIDTH = list_px(LIST_FALLBACK_WIDTH)
LIST_TITLE_FONT_POINT = font_px(LIST_TITLE_FONT_SIZE)
LIST_META_FONT_POINT = font_px(LIST_META_FONT_SIZE)
LIST_PLACEHOLDER_FONT_POINT = font_px(LIST_PLACEHOLDER_FONT_SIZE)
LIST_TITLE_BAND_HEIGHT = list_px(LIST_TITLE_BAND_HEIGHT)
LIST_META_BAND_HEIGHT = list_px(LIST_META_BAND_HEIGHT)
LIST_CARD_CORNER_RADIUS = list_px(LIST_CARD_CORNER_RADIUS)
LIST_THUMB_CORNER_RADIUS = list_px(LIST_THUMB_CORNER_RADIUS)
LIST_MIN_TEXT_WIDTH = list_px(LIST_MIN_TEXT_WIDTH)
LIST_ROW_INSET_X = list_px(LIST_ROW_INSET_X)
LIST_ROW_INSET_Y = list_px(LIST_ROW_INSET_Y)
GENRES_PER_ROW = 4
CARD_PADDING = detail_px(22)
RATING_CIRCLE_WIDGET_SIZE = detail_px(88)
RATING_CIRCLE_DIAMETER = detail_px(78)

POSTER_PLACEHOLDER_STYLE = build_poster_placeholder_style()
POSTER_IMAGE_STYLE = build_poster_image_style()
DETAIL_CARD_STYLE = build_detail_card_style()


@dataclass(frozen=True)
class DetailCardLayoutProfile:
    """Layout sizing for DetailCard (full watched view vs compact add-preview)."""

    poster_width: int
    poster_height: int
    poster_row_spacing: int
    card_padding: int
    rating_widget_size: int
    rating_circle_diameter: int
    rating_value_font_point: int
    rating_label_font_point: int
    show_user_score: bool = True
    show_recommendation_strength: bool = False
    show_mark_watched_button: bool = False
    show_hide_candidate_button: bool = False
    include_bottom_stretch: bool = True
    detail_hero_card_radius: int = detail_px(DETAIL_HERO_CARD_RADIUS)
    detail_hero_card_padding: int = detail_px(DETAIL_HERO_CARD_PADDING)
    detail_hero_card_padding_top: int = detail_px(DETAIL_HERO_CARD_PADDING_TOP)
    detail_hero_min_width: int = detail_px(DETAIL_HERO_MIN_WIDTH)
    detail_hero_preferred_min_width: int = detail_px(DETAIL_HERO_PREFERRED_MIN_WIDTH)
    detail_content_max_width: int = detail_px(DETAIL_CONTENT_MAX_WIDTH)
    detail_poster_width: int = detail_poster_px(DETAIL_POSTER_WIDTH)
    detail_poster_height: int = detail_poster_px(DETAIL_POSTER_HEIGHT)
    detail_poster_border_width: int = poster_px(DETAIL_POSTER_BORDER_WIDTH)
    detail_poster_radius: int = poster_px(DETAIL_POSTER_RADIUS)
    detail_poster_right_gap: int = compact_detail_px(DETAIL_POSTER_RIGHT_GAP, 24)
    detail_info_min_width: int = compact_detail_px(DETAIL_INFO_MIN_WIDTH, 280)
    detail_info_max_width: int = detail_px(DETAIL_INFO_MAX_WIDTH)
    detail_info_column_max_width: int = detail_px(DETAIL_INFO_COLUMN_MAX_WIDTH)
    detail_info_top_offset: int = detail_px(DETAIL_INFO_TOP_OFFSET)
    detail_title_font_family: str = DETAIL_TITLE_FONT_FAMILY
    detail_title_font_fallback: str = DETAIL_TITLE_FONT_FALLBACK
    detail_title_font_size: int = font_px(DETAIL_TITLE_FONT_SIZE)
    detail_title_line_height: int = detail_px(DETAIL_TITLE_LINE_HEIGHT)
    detail_title_max_lines: int = DETAIL_TITLE_MAX_LINES
    detail_chip_height: int = detail_px(DETAIL_CHIP_HEIGHT)
    detail_chip_radius: int = detail_px(DETAIL_CHIP_RADIUS)
    detail_chip_h_padding: int = detail_px(DETAIL_CHIP_H_PADDING)
    detail_chip_font_size: int = font_px(DETAIL_CHIP_FONT_SIZE)
    detail_chip_row_gap: int = detail_px(DETAIL_CHIP_ROW_GAP)
    detail_chip_col_gap: int = detail_px(DETAIL_CHIP_COL_GAP)
    detail_chip_max_rows: int = DETAIL_CHIP_MAX_ROWS
    detail_chip_max_width: int = detail_px(DETAIL_CHIP_MAX_WIDTH)
    detail_score_row_top_gap: int = detail_px(DETAIL_SCORE_ROW_TOP_GAP)
    detail_rating_widget_size: int = detail_px(DETAIL_RATING_WIDGET_SIZE)
    detail_rating_circle_diameter: int = detail_px(DETAIL_RATING_CIRCLE_DIAMETER)
    detail_stars_left_gap: int = detail_px(DETAIL_STARS_LEFT_GAP)
    detail_star_size: int = detail_px(DETAIL_STAR_SIZE)
    detail_star_gap: int = detail_px(DETAIL_STAR_GAP)
    detail_user_score_badge_min_width: int = detail_px(DETAIL_USER_SCORE_BADGE_MIN_WIDTH)
    detail_user_score_badge_height: int = detail_px(DETAIL_USER_SCORE_BADGE_HEIGHT)
    detail_user_score_badge_radius: int = detail_px(DETAIL_USER_SCORE_BADGE_RADIUS)
    detail_user_score_badge_top: int = detail_px(DETAIL_USER_SCORE_BADGE_TOP)
    detail_user_score_badge_left: int = detail_px(DETAIL_USER_SCORE_BADGE_LEFT)
    detail_user_score_badge_padding_x: int = detail_px(DETAIL_USER_SCORE_BADGE_PADDING_X)
    detail_main_info_top_gap: int = detail_px(DETAIL_MAIN_INFO_TOP_GAP)
    detail_main_info_panel_radius: int = detail_px(DETAIL_MAIN_INFO_PANEL_RADIUS)
    detail_main_info_panel_padding_x: int = detail_px(DETAIL_MAIN_INFO_PANEL_PADDING_X)
    detail_main_info_panel_padding_y: int = detail_px(DETAIL_MAIN_INFO_PANEL_PADDING_Y)
    detail_main_info_row_height: int = detail_px(DETAIL_MAIN_INFO_ROW_HEIGHT)
    detail_main_info_row_gap: int = detail_px(DETAIL_MAIN_INFO_ROW_GAP)
    detail_main_info_header_panel_gap: int = detail_px(DETAIL_MAIN_INFO_HEADER_PANEL_GAP)
    detail_main_info_label_width: int = detail_px(DETAIL_MAIN_INFO_LABEL_WIDTH)
    detail_overview_top_gap: int = detail_px(DETAIL_OVERVIEW_TOP_GAP)
    detail_overview_left_inset: int = detail_px(DETAIL_OVERVIEW_LEFT_INSET)
    detail_overview_title_top_gap: int = detail_px(DETAIL_OVERVIEW_TITLE_TOP_GAP)
    detail_overview_text_top_gap: int = detail_px(DETAIL_OVERVIEW_TEXT_TOP_GAP)
    detail_overview_max_lines_collapsed: int = DETAIL_OVERVIEW_MAX_LINES_COLLAPSED
    detail_overview_max_width: int = detail_px(DETAIL_OVERVIEW_MAX_WIDTH)
    detail_section_max_width: int = detail_px(DETAIL_SECTION_MAX_WIDTH)
    detail_additional_info_top_gap: int = detail_px(28)
    detail_divider_height: int = detail_px(1)
    detail_title_min_height: int = detail_px(36)
    detail_title_meta_gap: int = detail_px(4)
    detail_title_chips_gap: int = detail_px(DETAIL_TITLE_CHIPS_GAP)
    detail_column_spacing: int = detail_px(12)
    detail_small_spacing: int = detail_px(8)
    detail_micro_spacing: int = detail_px(DETAIL_SCORE_MAIN_INFO_GAP)
    detail_section_spacing: int = detail_px(DETAIL_SCORE_MAIN_INFO_GAP)
    detail_poster_actions_top_gap: int = detail_px(10)
    detail_candidate_action_button_size: int = detail_px(36)
    detail_candidate_action_icon_size: int = detail_px(24)
    detail_main_info_compact_padding_y_cap: int = detail_px(22)
    detail_main_info_compact_row_height: int = detail_px(38)
    detail_main_info_value_extra_height: int = detail_px(8)

    @property
    def detail_poster_content_width(self) -> int:
        return max(1, self.detail_poster_width - (2 * self.detail_poster_border_width))

    @property
    def detail_poster_content_height(self) -> int:
        return max(1, self.detail_poster_height - (2 * self.detail_poster_border_width))

    @property
    def detail_poster_content_radius(self) -> int:
        return max(0, self.detail_poster_radius - self.detail_poster_border_width)


DETAIL_CARD_LAYOUT_PROFILE = DetailCardLayoutProfile(
    poster_width=POSTER_WIDTH,
    poster_height=POSTER_HEIGHT,
    poster_row_spacing=POSTER_TOP_ROW_SPACING,
    card_padding=CARD_PADDING,
    rating_widget_size=RATING_CIRCLE_WIDGET_SIZE,
    rating_circle_diameter=RATING_CIRCLE_DIAMETER,
    rating_value_font_point=font_px(FONT_RATING_VALUE_POINT),
    rating_label_font_point=font_px(FONT_RATING_LABEL_POINT),
    show_user_score=True,
)

ADD_TITLE_PREVIEW_CARD_PROFILE = DetailCardLayoutProfile(
    poster_width=POSTER_WIDTH // 2,
    poster_height=POSTER_HEIGHT // 2,
    poster_row_spacing=max(detail_px(10), POSTER_TOP_ROW_SPACING // 2),
    card_padding=detail_px(14),
    rating_widget_size=detail_px(50),
    rating_circle_diameter=detail_px(44),
    rating_value_font_point=font_px(11),
    rating_label_font_point=font_px(7),
    show_user_score=False,
    include_bottom_stretch=False,
    detail_poster_width=POSTER_WIDTH // 2,
    detail_poster_height=POSTER_HEIGHT // 2,
)

CANDIDATE_DETAIL_CARD_PROFILE = replace(
    DETAIL_CARD_LAYOUT_PROFILE,
    show_user_score=False,
    show_recommendation_strength=True,
    show_mark_watched_button=False,
    show_hide_candidate_button=False,
)
