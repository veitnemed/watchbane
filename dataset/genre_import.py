"""Compatibility wrapper for KP API genre import."""

from dataset.genres.import_flow import (
    CONFIRM_NO,
    CONFIRM_YES,
    apply_genre_markup,
    ask_confirm,
    detect_genre_tags,
    extract_genres,
    format_tag_list,
    get_title,
    short_text,
)

__all__ = [
    "CONFIRM_NO",
    "CONFIRM_YES",
    "apply_genre_markup",
    "ask_confirm",
    "detect_genre_tags",
    "extract_genres",
    "format_tag_list",
    "get_title",
    "short_text",
]
