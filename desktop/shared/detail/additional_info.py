"""Additional-info formatter for title detail cards."""

from __future__ import annotations

from desktop.i18n import tr
from desktop.settings.app_settings import get_persisted_data_language
from dataset.language import normalize_data_language

from typing import Any


TMDB_STATUS_LABELS_RU = {
    "returning series": "Продолжается",
    "planned": "Запланирован",
    "in production": "В производстве",
    "ended": "Завершен",
    "canceled": "Отменен",
    "cancelled": "Отменен",
    "pilot": "Пилот",
}
TMDB_STATUS_LABELS_EN = {
    "returning series": "Returning series",
    "planned": "Planned",
    "in production": "In production",
    "ended": "Ended",
    "canceled": "Canceled",
    "cancelled": "Canceled",
    "pilot": "Pilot",
}

# Backward-compatible public constant.
TMDB_STATUS_LABELS = TMDB_STATUS_LABELS_RU


def _resolve_data_language(data_language: str | None = None) -> str:
    if data_language is None:
        data_language = get_persisted_data_language()
    return normalize_data_language(data_language)


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


def list_watch_provider_values(value: Any) -> list[str]:
    """Return normalized watch-provider names without formatting for a specific UI."""
    return _list_text_values(value)


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


def _plural_en(value: int, singular: str, plural: str) -> str:
    return singular if abs(value) == 1 else plural


def format_seasons_episodes(seasons: Any, episodes: Any, data_language: str | None = None) -> str | None:
    language = _resolve_data_language(data_language)
    seasons_count = _to_int(seasons)
    episodes_count = _to_int(episodes)
    parts: list[str] = []
    if seasons_count is not None and seasons_count > 0:
        if language == "en":
            parts.append(f"{seasons_count} {_plural_en(seasons_count, 'season', 'seasons')}")
        else:
            parts.append(f"{seasons_count} {_plural_ru(seasons_count, ('сезон', 'сезона', 'сезонов'))}")
    if episodes_count is not None and episodes_count > 0:
        if language == "en":
            parts.append(f"{episodes_count} {_plural_en(episodes_count, 'episode', 'episodes')}")
        else:
            parts.append(f"{episodes_count} {_plural_ru(episodes_count, ('серия', 'серии', 'серий'))}")
    return " / ".join(parts) if parts else None


def format_episode_runtime(value: Any, data_language: str | None = None) -> str | None:
    language = _resolve_data_language(data_language)
    unit = "min" if language == "en" else "мин"
    values = value if isinstance(value, (list, tuple, set)) else [value]
    minutes: list[int] = []
    for item in values:
        number = _to_int(item)
        if number is not None and number > 0 and number not in minutes:
            minutes.append(number)
    if not minutes:
        return None
    if len(minutes) == 1:
        return f"{minutes[0]} {unit}"
    return ", ".join(f"{item} {unit}" for item in minutes[:3])


def format_watch_providers(value: Any) -> str | None:
    providers = _list_text_values(value)
    return ", ".join(providers[:6]) if providers else None


def format_tmdb_status(status: Any, in_production: Any = None, data_language: str | None = None) -> str | None:
    language = _resolve_data_language(data_language)
    labels = TMDB_STATUS_LABELS_EN if language == "en" else TMDB_STATUS_LABELS_RU
    text = _clean_text(status)
    if text is not None:
        return labels.get(text.casefold(), text)
    if in_production is True:
        return "In production" if language == "en" else "В производстве"
    if in_production is False:
        return "Not in production" if language == "en" else "Не в производстве"
    return None


def build_additional_info_items(card: dict, data_language: str | None = None) -> list[dict[str, str]]:
    """Build compact rows for the title additional-info block."""
    items: list[dict[str, str]] = []
    language = _resolve_data_language(data_language)

    status = format_tmdb_status(
        card.get("status") or card.get("tmdb_status"),
        card.get("in_production"),
        data_language=language,
    )
    if status is not None:
        items.append({"label": tr("detail.info.status"), "value": status})

    runtime = format_episode_runtime(
        card.get("episode_run_time") or card.get("runtime_minutes"),
        data_language=language,
    )
    if runtime is not None:
        items.append({"label": tr("detail.info.runtime"), "value": runtime})

    return [item for item in items if _has_value(item.get("value"))]
