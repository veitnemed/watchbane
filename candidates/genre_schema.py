"""Canonical genre keys and display labels for candidate-pool records."""

from __future__ import annotations

from typing import Any


GENRE_KEY_TO_DISPLAY: dict[str, str] = {
    "drama": "Драма",
    "comedy": "Комедия",
    "romance": "Мелодрама",
    "biography": "Биография",
    "history": "История",
    "crime": "Криминал",
    "mystery": "Детектив",
    "thriller": "Триллер",
    "horror": "Ужасы",
    "action_adventure": "Боевик/приключения",
    "sci_fi_fantasy": "Фантастика/фэнтези",
    "animation": "Анимация",
    "family": "Семейный",
    "war": "Военный",
    "western": "Вестерн",
    "music": "Музыка",
    "musical": "Мюзикл",
    "documentary": "Документальный",
    "sport": "Спорт",
    "reality": "Реалити",
    "talk_show": "Ток-шоу",
    "news": "Новости",
    "game_show": "Телеигра",
    "short": "Короткометражка",
    "film_noir": "Нуар",
}

_GENRE_ALIASES_BY_KEY: dict[str, list[str]] = {
    "drama": ["drama", "драма"],
    "comedy": ["comedy", "комедия"],
    "romance": ["romance", "мелодрама", "романтика"],
    "biography": ["biography", "биография"],
    "history": ["history", "история"],
    "crime": ["crime", "криминал", "преступление", "преступления"],
    "mystery": ["mystery", "детектив", "мистика"],
    "thriller": ["thriller", "триллер"],
    "horror": ["horror", "ужасы"],
    "action_adventure": [
        "action",
        "adventure",
        "action & adventure",
        "action and adventure",
        "боевик",
        "приключения",
        "боевик и приключения",
    ],
    "sci_fi_fantasy": [
        "fantasy",
        "sci fi",
        "sci-fi",
        "sci fi fantasy",
        "sci-fi & fantasy",
        "sci-fi and fantasy",
        "science fiction",
        "фантастика",
        "фэнтези",
        "научная фантастика",
        "нф и фэнтези",
    ],
    "animation": ["animation", "анимация", "мультфильм", "мультфильмы"],
    "family": ["family", "семейный"],
    "war": ["war", "военный"],
    "western": ["western", "вестерн"],
    "music": ["music", "музыка"],
    "musical": ["musical", "мюзикл"],
    "documentary": ["documentary", "документальный"],
    "sport": ["sport", "спорт"],
    "reality": ["reality", "reality tv", "reality-tv", "реалити", "реалити-шоу"],
    "talk_show": ["talk", "talk show", "talk-show", "ток-шоу", "ток шоу"],
    "news": ["news", "новости"],
    "game_show": ["game show", "game-show", "телеигра"],
    "short": ["short", "короткометражка"],
    "film_noir": ["film noir", "film-noir", "нуар"],
}

GENRE_ALIAS_TO_KEY: dict[str, str] = {}


def _normalize_alias(value: str) -> str:
    text = str(value or "").strip().casefold()
    text = text.replace("ё", "е")
    text = text.replace("-", " ")
    text = text.replace("&", " and ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


for _genre_key, _aliases in _GENRE_ALIASES_BY_KEY.items():
    GENRE_ALIAS_TO_KEY[_normalize_alias(_genre_key)] = _genre_key
    for _alias in _aliases:
        GENRE_ALIAS_TO_KEY[_normalize_alias(_alias)] = _genre_key


def normalize_genre_to_key(value: str) -> str | None:
    """Maps one raw genre label to canonical genre key, or None if unknown."""
    normalized = _normalize_alias(value)
    if normalized == "":
        return None
    return GENRE_ALIAS_TO_KEY.get(normalized)


def _iter_raw_genres(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        parts = [item.strip() for item in values.split(",")]
        return [item for item in parts if item != ""]
    if isinstance(values, (list, tuple, set)):
        result = []
        for item in values:
            text = str(item or "").strip()
            if text != "":
                result.append(text)
        return result
    text = str(values).strip()
    return [text] if text != "" else []


def normalize_genre_filter_list(values) -> list[str]:
    """Normalizes user/runtime genre filters to ordered unique canonical keys."""
    keys: list[str] = []
    seen: set[str] = set()
    for raw_value in _iter_raw_genres(values):
        genre_key = normalize_genre_to_key(raw_value)
        if genre_key is None or genre_key in seen:
            continue
        seen.add(genre_key)
        keys.append(genre_key)
    return keys


def genre_keys_match_any(candidate_keys: list[str], required_keys: list[str]) -> bool:
    """True when candidate genre_keys intersect required canonical keys."""
    if len(required_keys) == 0:
        return True
    return len(set(candidate_keys) & set(required_keys)) > 0


def genre_keys_match_none(candidate_keys: list[str], excluded_keys: list[str]) -> bool:
    """True when candidate genre_keys do not intersect excluded canonical keys."""
    if len(excluded_keys) == 0:
        return True
    return len(set(candidate_keys) & set(excluded_keys)) == 0


def build_genre_keys(candidate: dict) -> list[str]:
    """Builds ordered unique genre keys from imdb_genres, genres_tmdb, then legacy genres."""
    raw_values: list[str] = []
    for field_name in ("imdb_genres", "genres_tmdb", "genres"):
        raw_values.extend(_iter_raw_genres(candidate.get(field_name)))

    keys: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        genre_key = normalize_genre_to_key(raw_value)
        if genre_key is None or genre_key in seen:
            continue
        seen.add(genre_key)
        keys.append(genre_key)
    return keys


def build_genres_display(genre_keys: list[str]) -> list[str]:
    """Maps canonical genre keys to Russian UI labels."""
    labels: list[str] = []
    seen: set[str] = set()
    for genre_key in genre_keys:
        label = GENRE_KEY_TO_DISPLAY.get(genre_key)
        if label is None or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels


def candidate_genres_for_display(candidate: dict) -> list[str]:
    """Returns UI genre labels, preferring genres_display with legacy fallback."""
    display = _iter_raw_genres(candidate.get("genres_display"))
    if len(display) > 0:
        return display
    return _iter_raw_genres(candidate.get("genres"))
