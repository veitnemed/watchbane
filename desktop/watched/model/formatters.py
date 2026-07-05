"""Watched list and filter UI formatters (no Qt)."""

from __future__ import annotations

from desktop.shared.detail.presenters import format_user_score_display, format_year_display
from desktop.watched.model.filters import watched_filters_are_active


def format_list_label(card: dict) -> str:
    """Compact label for the left-hand list."""
    title = card.get("title") or "Без названия"
    year = card.get("year")
    score_label = format_user_score_display(card.get("user_score"))
    parts = [title]
    year_label = format_year_display(year)
    if year_label:
        parts.append(f"({year_label})")
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
        return "Ничего не найдено" if has_filter else "Список пуст"
    if has_filter:
        return f"Показано {visible_count} из {total_count}"
    return f"Всего {visible_count}"


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
        return "Ничего не найдено" if has_filter else "Список пуст"
    if has_filter or visible_count != total_count:
        return f"{visible_count} из {total_count}"
    return f"Всего {visible_count}"


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
        return f"{arrow} Фильтры активны"
    return f"{arrow} Фильтры"
