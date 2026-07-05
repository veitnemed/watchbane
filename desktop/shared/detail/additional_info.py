"""Additional-info formatter for title detail cards."""

from __future__ import annotations

from typing import Any


TMDB_STATUS_LABELS = {
    "returning series": "Продолжается",
    "planned": "Запланирован",
    "in production": "В производстве",
    "ended": "Завершен",
    "canceled": "Отменен",
    "cancelled": "Отменен",
    "pilot": "Пилот",
}


def _has_value(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return value is not None and str(value).strip() != ""


def _clean_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text if text else None


def _to_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _list_text_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]

    result: list[str] = []
    for item in items:
        if isinstance(item, dict):
            text = _clean_text(item.get("name") or item.get("provider_name") or item.get("label"))
        else:
            text = _clean_text(item)
        if text is not None and text not in result:
            result.append(text)
    return result


def _plural_ru(value: int, forms: tuple[str, str, str]) -> str:
    value_abs = abs(value)
    if value_abs % 100 in range(11, 15):
        return forms[2]
    last_digit = value_abs % 10
    if last_digit == 1:
        return forms[0]
    if last_digit in (2, 3, 4):
        return forms[1]
    return forms[2]


def format_seasons_episodes(seasons: Any, episodes: Any) -> str | None:
    seasons_count = _to_int(seasons)
    episodes_count = _to_int(episodes)
    parts: list[str] = []
    if seasons_count is not None and seasons_count > 0:
        parts.append(f"{seasons_count} {_plural_ru(seasons_count, ('сезон', 'сезона', 'сезонов'))}")
    if episodes_count is not None and episodes_count > 0:
        parts.append(f"{episodes_count} {_plural_ru(episodes_count, ('серия', 'серии', 'серий'))}")
    return " / ".join(parts) if parts else None


def format_episode_runtime(value: Any) -> str | None:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    minutes: list[int] = []
    for item in values:
        number = _to_int(item)
        if number is not None and number > 0 and number not in minutes:
            minutes.append(number)
    if not minutes:
        return None
    if len(minutes) == 1:
        return f"{minutes[0]} мин"
    return ", ".join(f"{item} мин" for item in minutes[:3])


def format_watch_providers(value: Any) -> str | None:
    providers = _list_text_values(value)
    return ", ".join(providers[:6]) if providers else None


def format_tmdb_status(status: Any, in_production: Any = None) -> str | None:
    text = _clean_text(status)
    if text is not None:
        return TMDB_STATUS_LABELS.get(text.casefold(), text)
    if in_production is True:
        return "В производстве"
    if in_production is False:
        return "Не в производстве"
    return None


def build_additional_info_items(card: dict) -> list[dict[str, str]]:
    """Build compact rows for the title additional-info block."""
    items: list[dict[str, str]] = []

    status = format_tmdb_status(card.get("status") or card.get("tmdb_status"), card.get("in_production"))
    if status is not None:
        items.append({"label": "Статус", "value": status})

    runtime = format_episode_runtime(card.get("episode_run_time") or card.get("runtime_minutes"))
    if runtime is not None:
        items.append({"label": "Длительность серии", "value": runtime})

    return [item for item in items if _has_value(item.get("value"))]
