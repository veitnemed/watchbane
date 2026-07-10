"""Candidate completeness helpers and genre list utilities."""

from __future__ import annotations

from candidates.models import genre_schema
from candidates.models.schema import is_candidate_complete as schema_is_candidate_complete


def normalize_genre_list(raw_value: str) -> list:
    """Нормализует строку жанров через запятую."""
    genres = []
    for item in str(raw_value or "").split(","):
        genre = item.strip()
        if genre != "":
            genres.append(genre)
    return genres


def get_available_genres() -> list:
    """Возвращает список доступных жанров для выбора в критериях."""
    return sorted(set(genre_schema.GENRE_KEY_TO_DISPLAY.values()))


def is_candidate_complete(candidate: dict) -> bool:
    """Проверяет, достаточно ли у кандидата рейтинговых данных для строгого поиска."""
    return schema_is_candidate_complete(candidate)


def append_signal(candidate: dict, signal: str) -> None:
    """Добавляет signal кандидату без дублей."""
    signals = candidate.setdefault("signals", [])
    if signal not in signals:
        signals.append(signal)


def movie_matches_genres(movie: dict, expected_genres: list, excluded_genres: list | None = None) -> bool:
    """Проверяет обязательные и исключенные жанры кандидата."""
    if excluded_genres is None:
        excluded_genres = []
    actual = {
        str(item.get("name", "")).strip().casefold()
        for item in movie.get("genres", []) or []
        if isinstance(item, dict) and item.get("name")
    }
    blocked = {genre.casefold() for genre in excluded_genres}
    if len(actual & blocked) > 0:
        return False
    if len(expected_genres) == 0:
        return True
    wanted = {genre.casefold() for genre in expected_genres}
    return len(actual & wanted) > 0
