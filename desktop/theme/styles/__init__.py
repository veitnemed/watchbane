"""QSS builder functions grouped by screen area."""

from desktop.theme.styles.analytics import build_analytics_style
from desktop.theme.styles.app import build_app_style
from desktop.theme.styles.detail_card import (
    build_bar_fill_style,
    build_bar_track_style,
    build_detail_card_style,
    build_poster_image_style,
    build_poster_placeholder_style,
)
from desktop.theme.styles.dialogs import (
    build_add_title_dialog_style,
    build_delete_dialog_style,
    build_score_edit_dialog_style,
)
from desktop.theme.styles.settings import build_settings_style

__all__ = [
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
