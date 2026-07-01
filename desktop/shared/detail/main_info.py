"""Main-info formatter for title detail cards."""

from __future__ import annotations


UNKNOWN_OBJECT_TYPE = "Неизвестно"


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

    country = _clean_text(card.get("country"))
    if country is not None:
        items.append({"label": "Страна", "value": country})

    items.append(
        {
            "label": "Тип",
            "value": normalize_object_type(card.get("object_type"), card),
        }
    )

    imdb_votes = format_votes_display(card.get("imdb_votes"))
    if imdb_votes is not None:
        items.append({"label": "Голоса IMDb", "value": imdb_votes})

    kp_votes = format_votes_display(card.get("kp_votes"))
    if kp_votes is not None:
        items.append({"label": "Голоса КП", "value": kp_votes})

    return items
