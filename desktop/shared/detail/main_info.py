"""Main-info formatter for title detail cards."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from candidates.models import country_schema
from dataset.language import normalize_data_language
from desktop.i18n import tr
from desktop.settings.app_settings import get_persisted_data_language
from desktop.shared.detail.additional_info import (
    build_additional_info_items,
    format_runtime_minutes,
    format_seasons_episodes,
    list_watch_provider_values,
)
from dataset.models.media_type import MEDIA_TYPE_MOVIE, normalize_media_type
from desktop.shared.detail.presenters import format_year_display


UNKNOWN_OBJECT_TYPE = "Неизвестно"
NO_DATA_LABEL = "Неизвестно"
WATCH_PROVIDER_VISIBLE_COUNT = 2
MONTH_LABELS_RU = {
    1: "янв",
    2: "фев",
    3: "мар",
    4: "апр",
    5: "май",
    6: "июн",
    7: "июл",
    8: "авг",
    9: "сен",
    10: "окт",
    11: "ноя",
    12: "дек",
}
MONTH_LABELS_EN = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


def _resolve_data_language(data_language: str | None = None) -> str:
    if data_language is None:
        data_language = get_persisted_data_language()
    return normalize_data_language(data_language)


def _unknown_object_type_label(language: str) -> str:
    return "Unknown" if language == "en" else UNKNOWN_OBJECT_TYPE


def _no_data_label(language: str) -> str:
    return "Unknown" if language == "en" else NO_DATA_LABEL


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


def normalize_object_type(value, card: dict | None = None, data_language: str | None = None) -> str:
    """Return user-facing object type for detail-card display."""
    language = _resolve_data_language(data_language)
    text = _clean_text(value)
    lowered = text.casefold() if text is not None else ""

    if lowered in {"movie", "film", "tvmovie", "tv movie", "фильм"}:
        return "Movie" if language == "en" else "Фильм"
    if lowered in {"tv", "series", "serial", "show", "tvseries", "tv series", "tvminiseries", "сериал"}:
        return "Series" if language == "en" else "Сериал"
    if lowered in {"unknown", "n/a", "na", "none", "null", "-"}:
        return _unknown_object_type_label(language)
    if text is None and isinstance(card, dict) and _has_tv_shape(card):
        return "Series" if language == "en" else "Сериал"
    return text or _unknown_object_type_label(language)


def _capitalize_display_value(value) -> str:
    text = _clean_text(value)
    if text is None:
        return ""
    return f"{text[:1].upper()}{text[1:]}"


def _format_compact_thousands(value: int, *, suffix: str = "к") -> str:
    compact = (Decimal(value) / Decimal(1000)).quantize(
        Decimal("0.1"),
        rounding=ROUND_HALF_UP,
    )
    text = format(compact, "f").rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def format_votes_display(value, data_language: str | None = None) -> str | None:
    language = _resolve_data_language(data_language)
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        votes = int(value)
    except (TypeError, ValueError):
        return None
    if votes <= 0:
        return None
    if votes < 10:
        return "Very few" if language == "en" else "Крайне мало"
    if votes < 100:
        return "0.1k" if language == "en" else "0.1к"
    return _format_compact_thousands(votes, suffix="k" if language == "en" else "к")


def format_air_date_display(value, data_language: str | None = None) -> str | None:
    language = _resolve_data_language(data_language)
    text = _clean_text(value)
    if text is None:
        return None
    try:
        parsed = date.fromisoformat(text[:10])
    except ValueError:
        return None
    month_labels = MONTH_LABELS_EN if language == "en" else MONTH_LABELS_RU
    month = month_labels.get(parsed.month)
    if month is None:
        return None
    return f"{parsed.day} {month} {parsed.year}"


def _last_episode_air_date(card: dict, data_language: str | None = None) -> str | None:
    episode = card.get("last_episode_to_air")
    if isinstance(episode, dict):
        air_date = format_air_date_display(episode.get("air_date"), data_language=data_language)
        if air_date is not None:
            return air_date
    return format_air_date_display(card.get("last_air_date"), data_language=data_language)


def _build_watch_provider_item(value, data_language: str | None = None) -> dict[str, object]:
    language = _resolve_data_language(data_language)
    providers = [_capitalize_display_value(provider) for provider in list_watch_provider_values(value)]
    providers = [provider for provider in providers if provider]
    if not providers:
        return {"label": tr("detail.info.watch_where"), "value": _no_data_label(language)}

    visible_providers = providers[:WATCH_PROVIDER_VISIBLE_COUNT]
    hidden_providers = providers[WATCH_PROVIDER_VISIBLE_COUNT:]
    item: dict[str, object] = {
        "label": tr("detail.info.watch_where"),
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


def build_main_info_items(card: dict, data_language: str | None = None) -> list[dict[str, object]]:
    """Build compact label/value rows for the title main-info block."""
    items: list[dict[str, object]] = []
    language = _resolve_data_language(data_language)

    items.append(
        {
            "label": tr("detail.info.type"),
            "value": normalize_object_type(card.get("object_type") or card.get("media_type"), card, data_language=language),
        }
    )

    country = _clean_text(card.get("country"))
    if country is not None:
        country_codes = country_schema.normalize_country_filter_list(country)
        country = country_schema.build_country_display(
            country_codes,
            language=language,
        ) or country
        items.append({"label": tr("detail.info.country"), "value": country})

    first_air_date = format_air_date_display(card.get("first_air_date"), data_language=language)
    if first_air_date is not None:
        items.append({"label": tr("detail.info.premiere"), "value": first_air_date})

    last_episode = _last_episode_air_date(card, data_language=language)
    if last_episode is not None:
        items.append({"label": tr("detail.info.last_episode"), "value": last_episode})

    provider_source = card.get("watch_providers") or card.get("watch_providers_ru")
    items.append(_build_watch_provider_item(provider_source, data_language=language))

    tmdb_votes = format_votes_display(card.get("tmdb_votes"), data_language=language)
    if tmdb_votes is not None:
        items.append({"label": tr("detail.info.tmdb_votes"), "value": tmdb_votes})

    items.extend(build_additional_info_items(card, data_language=language))

    return [_normalize_main_info_item(item) for item in items]


def build_title_meta_text(card: dict, data_language: str | None = None) -> str:
    """Build title subtitle text like '2020 • 2 сезона / 20 серий'."""
    parts = []
    language = _resolve_data_language(data_language)

    year = format_year_display(card.get("year"))
    if year:
        parts.append(year)

    if _is_movie_card(card):
        runtime = format_runtime_minutes(_movie_runtime_value(card), data_language=language)
        if runtime is not None:
            parts.append(runtime)
        return " • ".join(parts)

    seasons_episodes = format_seasons_episodes(
        card.get("number_of_seasons"),
        card.get("number_of_episodes"),
        data_language=language,
    )
    if seasons_episodes is not None:
        parts.append(seasons_episodes)

    return " • ".join(parts)


def _is_movie_card(card: dict) -> bool:
    if normalize_media_type(card.get("media_type")) == MEDIA_TYPE_MOVIE:
        return True
    text = _clean_text(card.get("object_type"))
    return text is not None and text.casefold() in {"movie", "film", "tvmovie", "tv movie", "фильм"}


def _movie_runtime_value(card: dict):
    for field_name in ("runtime", "runtime_minutes", "imdb_runtime_minutes"):
        value = card.get(field_name)
        if value not in (None, ""):
            return value
    return None
