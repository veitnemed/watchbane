"""Watched list and filter UI formatters (no Qt)."""

from __future__ import annotations

from desktop.i18n import tr
from desktop.shared.detail.presenters import format_user_score_display, format_year_display
from desktop.watched.model.filters import watched_filters_are_active
from dataset.models.media_type import MEDIA_TYPE_MOVIE, normalize_media_type


def format_list_label(card: dict) -> str:
    """Compact label for the left-hand list."""
    title = card.get("title") or tr("common.untitled")
    year = card.get("year")
    score_label = format_user_score_display(card.get("user_score"))
    parts = [title]
    year_label = format_year_display(year)
    if year_label:
        parts.append(f"({year_label})")
    if "media_type" in card:
        media_type = normalize_media_type(card.get("media_type"))
        type_label = "Movie" if media_type == MEDIA_TYPE_MOVIE else "Series"
        parts.append(f"· {type_label}")
    label = " ".join(parts)
    if score_label != "—":
        label = f"{label}  ·  {score_label}"
    return label


def format_watched_list_status(
    visible_count: int,
    total_count: int,
    query: str = "",
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
) -> str:
    """Status bar text for watched list filter results."""
    normalized = query.strip()
    has_filter = bool(normalized) or has_score_filter or has_year_filter or has_genre_filter
    if visible_count == 0:
        return tr("watched.status.no_results") if has_filter else tr("watched.status.empty")
    if has_filter:
        return tr("watched.status.shown", visible=visible_count, total=total_count)
    return tr("watched.status.total", visible=visible_count)


def format_watched_list_counter(
    visible_count: int,
    total_count: int,
    query: str = "",
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
) -> str:
    """Compact counter shown above the watched list."""
    normalized = query.strip()
    has_filter = bool(normalized) or has_score_filter or has_year_filter or has_genre_filter
    if visible_count == 0:
        return tr("watched.status.no_results") if has_filter else tr("watched.status.empty")
    if has_filter or visible_count != total_count:
        return tr("watched.status.visible_total", visible=visible_count, total=total_count)
    return tr("watched.status.total", visible=visible_count)


def count_active_filters(
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
) -> int:
    """Return the number of active score/year/genre filters (search excluded)."""
    return int(has_score_filter) + int(has_year_filter) + int(has_genre_filter)


def format_watched_filters_label(
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
    is_expanded: bool = False,
) -> str:
    """Build the watched filters toggle label for the sidebar."""
    arrow = "▾" if is_expanded else "▸"
    if watched_filters_are_active(has_score_filter, has_year_filter, has_genre_filter):
        return f"{arrow} {tr('watched.filters.active')}"
    return f"{arrow} {tr('watched.filters.toggle')}"
