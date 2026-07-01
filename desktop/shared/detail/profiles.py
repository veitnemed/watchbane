"""Layout profiles and sizing constants for detail cards."""

from __future__ import annotations

from dataclasses import dataclass, replace

from desktop.theme import (
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
)

CANDIDATE_DETAIL_CARD_PROFILE = replace(
    DETAIL_CARD_LAYOUT_PROFILE,
    show_user_score=False,
    show_mark_watched_button=True,
    show_hide_candidate_button=True,
)
