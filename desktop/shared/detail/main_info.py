"""Main-info formatter for title detail cards."""

from __future__ import annotations

from candidates.models import country_schema
from desktop.shared.detail.additional_info import (
    build_additional_info_items,
    format_seasons_episodes,
    format_watch_providers,
)
from desktop.shared.detail.presenters import format_year_display


UNKNOWN_OBJECT_TYPE = "Неизвестно"
NO_DATA_LABEL = "нет данных"


def _clean_text(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text if text else None


def _has_tv_shape(card: dict) -> bool:
    for field_name in ("number_of_seasons", "number_of_episodes"):
        value = card.get(field_name)
        if value in (None, "", 0, "0"):
            continue
        return True
    return False


def normalize_object_type(value, card: dict | None = None) -> str:
    """Return user-facing object type for detail-card display."""
    text = _clean_text(value)
    lowered = text.casefold() if text is not None else ""

    if lowered in {"movie", "film", "tvmovie", "tv movie", "фильм"}:
        return "Фильм"
    if lowered in {"tv", "series", "serial", "show", "tvseries", "tv series", "tvminiseries", "сериал"}:
        return "Сериал"
    if lowered in {"unknown", "n/a", "na", "none", "null", "-"}:
        return UNKNOWN_OBJECT_TYPE
    if text is None and isinstance(card, dict) and _has_tv_shape(card):
        return "Сериал"
    return text or UNKNOWN_OBJECT_TYPE


def format_votes_display(value) -> str | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        votes = int(value)
    except (TypeError, ValueError):
        return None
    if votes <= 0:
        return None
    return f"{votes:,}".replace(",", " ")


def build_main_info_items(card: dict) -> list[dict[str, str]]:
    """Build compact label/value rows for the title main-info block."""
    items: list[dict[str, str]] = []

    items.append(
        {
            "label": "Тип",
            "value": normalize_object_type(card.get("object_type"), card),
        }
    )

    country = _clean_text(card.get("country"))
    if country is not None:
        country = country_schema.build_country_display(
            country_schema.normalize_country_filter_list(country)
        ) or country
        items.append({"label": "Страна", "value": country})

    providers = format_watch_providers(card.get("watch_providers") or card.get("watch_providers_ru"))
    items.append({"label": "Где смотреть", "value": providers or NO_DATA_LABEL})

    tmdb_votes = format_votes_display(card.get("tmdb_votes"))
    if tmdb_votes is not None:
        items.append({"label": "Голоса TMDb", "value": tmdb_votes})

    items.extend(build_additional_info_items(card))

    return items


def build_title_meta_text(card: dict) -> str:
    """Build title subtitle text like '2020 • 2 сезона / 20 серий'."""
    parts = []

    year = format_year_display(card.get("year"))
    if year:
        parts.append(year)

    seasons_episodes = format_seasons_episodes(
        card.get("number_of_seasons"),
        card.get("number_of_episodes"),
    )
    if seasons_episodes is not None:
        parts.append(seasons_episodes)

    return " • ".join(parts)
