"""Main-info formatter for title detail cards."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from candidates.models import country_schema
from desktop.shared.detail.additional_info import (
    build_additional_info_items,
    format_seasons_episodes,
    list_watch_provider_values,
)
from desktop.shared.detail.presenters import format_year_display


UNKNOWN_OBJECT_TYPE = "Неизвестно"
NO_DATA_LABEL = "Неизвестно"
WATCH_PROVIDER_VISIBLE_COUNT = 2


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


def _capitalize_display_value(value) -> str:
    text = _clean_text(value)
    if text is None:
        return ""
    return f"{text[:1].upper()}{text[1:]}"


def _format_compact_thousands(value: int) -> str:
    compact = (Decimal(value) / Decimal(1000)).quantize(
        Decimal("0.1"),
        rounding=ROUND_HALF_UP,
    )
    text = format(compact, "f").rstrip("0").rstrip(".")
    return f"{text}к"


def format_votes_display(value) -> str | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        votes = int(value)
    except (TypeError, ValueError):
        return None
    if votes <= 0:
        return None
    if votes < 10:
        return "Крайне мало"
    if votes < 100:
        return "0.1к"
    return _format_compact_thousands(votes)


def _build_watch_provider_item(value) -> dict[str, object]:
    providers = [_capitalize_display_value(provider) for provider in list_watch_provider_values(value)]
    providers = [provider for provider in providers if provider]
    if not providers:
        return {"label": "Где смотреть", "value": NO_DATA_LABEL}

    visible_providers = providers[:WATCH_PROVIDER_VISIBLE_COUNT]
    hidden_providers = providers[WATCH_PROVIDER_VISIBLE_COUNT:]
    item: dict[str, object] = {
        "label": "Где смотреть",
        "value": ", ".join(visible_providers),
    }
    if hidden_providers:
        item["value"] = f"{item['value']} +{len(hidden_providers)}"
        item["tooltip"] = ", ".join(hidden_providers)
    return item


def _normalize_main_info_item(item: dict[str, object]) -> dict[str, object]:
    normalized = dict(item)
    normalized["value"] = _capitalize_display_value(normalized.get("value", ""))
    tooltip = _clean_text(normalized.get("tooltip"))
    if tooltip is None:
        normalized.pop("tooltip", None)
    else:
        normalized["tooltip"] = tooltip
    return normalized


def build_main_info_items(card: dict) -> list[dict[str, object]]:
    """Build compact label/value rows for the title main-info block."""
    items: list[dict[str, object]] = []

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

    provider_source = card.get("watch_providers") or card.get("watch_providers_ru")
    items.append(_build_watch_provider_item(provider_source))

    tmdb_votes = format_votes_display(card.get("tmdb_votes"))
    if tmdb_votes is not None:
        items.append({"label": "Голоса TMDb", "value": tmdb_votes})

    items.extend(build_additional_info_items(card))

    return [_normalize_main_info_item(item) for item in items]


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
