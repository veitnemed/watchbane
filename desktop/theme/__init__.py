"""Desktop theme: tokens and QSS builders."""

from desktop.theme import tokens
from desktop.theme.styles import (
    build_add_title_dialog_style,
    build_analytics_style,
    build_app_style,
    build_bar_fill_style,
    build_bar_track_style,
    build_delete_dialog_style,
    build_detail_card_style,
    build_poster_image_style,
    build_poster_placeholder_style,
    build_score_edit_dialog_style,
    build_settings_style,
)

__all__ = [
    *tokens.__all__,
    "build_add_title_dialog_style",
    "build_analytics_style",
    "build_app_style",
    "build_bar_fill_style",
    "build_bar_track_style",
    "build_delete_dialog_style",
    "build_detail_card_style",
    "build_poster_image_style",
    "build_poster_placeholder_style",
    "build_score_edit_dialog_style",
    "build_settings_style",
]

globals().update({name: getattr(tokens, name) for name in tokens.__all__})
