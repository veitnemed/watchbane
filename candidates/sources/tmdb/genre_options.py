"""TMDb TV genre options for Discover filters.

This module is intentionally separate from candidates.genres: these IDs are
for new TMDb Discover requests, not runtime matching over saved pool data.
"""

from __future__ import annotations

from typing import Any


TMDB_DISCOVER_GENRE_TITLE = "Жанры для поиска (TMDb)"
TMDB_INCLUDE_OR_LABEL = "Любой из выбранных жанров (TMDb OR)"
TMDB_INCLUDE_AND_LABEL = "Все выбранные жанры одновременно (TMDb AND)"
TMDB_EXCLUDE_LABEL = "Exclude жанры (TMDb)"

MODE_OR = "or"
MODE_AND = "and"

INCLUDE_TV_GENRE_OPTIONS: list[dict[str, Any]] = [
    {"id": 18, "label": "Драма", "tmdb_name": "Drama"},
    {"id": 9648, "label": "Детектив / мистика", "tmdb_name": "Mystery"},
    {"id": 80, "label": "Криминал", "tmdb_name": "Crime"},
    {"id": 35, "label": "Комедия", "tmdb_name": "Comedy"},
    {"id": 10759, "label": "Боевик / приключения", "tmdb_name": "Action & Adventure"},
    {"id": 10765, "label": "Фантастика / фэнтези", "tmdb_name": "Sci-Fi & Fantasy"},
    {"id": 16, "label": "Анимация", "tmdb_name": "Animation"},
]

EXCLUDE_TV_GENRE_OPTIONS: list[dict[str, Any]] = [
    {"id": 10766, "label": "Мыльная опера", "tmdb_name": "Soap"},
    {"id": 10764, "label": "Реалити", "tmdb_name": "Reality"},
    {"id": 10767, "label": "Ток-шоу", "tmdb_name": "Talk"},
    {"id": 10763, "label": "Новости", "tmdb_name": "News"},
    {"id": 10762, "label": "Детское", "tmdb_name": "Kids"},
    {"id": 99, "label": "Документальное", "tmdb_name": "Documentary"},
]

TV_GENRE_OPTIONS: list[dict[str, Any]] = INCLUDE_TV_GENRE_OPTIONS + EXCLUDE_TV_GENRE_OPTIONS
_LABEL_BY_ID = {int(option["id"]): str(option["label"]) for option in TV_GENRE_OPTIONS}


def build_filter_value(genre_ids: list[int], mode: str = MODE_OR) -> str | None:
    cleaned_ids = [int(genre_id) for genre_id in genre_ids if genre_id is not None]
    if len(cleaned_ids) == 0:
        return None
    separator = "," if mode == MODE_AND else "|"
    return separator.join(str(genre_id) for genre_id in cleaned_ids)


def genre_ids_from_indexes(indexes: list[int], options: list[dict[str, Any]] | None = None) -> list[int]:
    options = options or TV_GENRE_OPTIONS
    selected_ids = []
    for index in indexes:
        if 1 <= index <= len(options):
            genre_id = int(options[index - 1]["id"])
            if genre_id not in selected_ids:
                selected_ids.append(genre_id)
    return selected_ids


def labels_from_ids(genre_ids: list[int]) -> list[str]:
    return [_LABEL_BY_ID.get(int(genre_id), str(genre_id)) for genre_id in genre_ids]


def describe_filter_value(value: str | None) -> str:
    text = str(value or "").strip()
    if text == "":
        return "без фильтра"

    if "|" in text:
        separator = "|"
        label_separator = " OR "
    elif "," in text:
        separator = ","
        label_separator = " AND "
    else:
        separator = None
        label_separator = ""

    parts = [text] if separator is None else [item.strip() for item in text.split(separator)]
    labels = []
    for part in parts:
        try:
            genre_id = int(part)
        except ValueError:
            labels.append(part)
            continue
        labels.append(_LABEL_BY_ID.get(genre_id, part))
    return label_separator.join(label for label in labels if label)
