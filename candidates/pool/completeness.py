"""Candidate completeness helpers and genre list utilities."""

from __future__ import annotations

from config import genre_tags

from candidates.schema import is_candidate_complete as schema_is_candidate_complete


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
    tags = genre_tags.load_genre_tags()
    genres = []
    for settings in tags.values():
        source = str(settings.get("source", "")).strip()
        if source != "":
            genres.append(source)
    return sorted(set(genres))


def is_candidate_complete(candidate: dict) -> bool:
    """Проверяет, достаточно ли у кандидата рейтинговых данных для строгого поиска."""
    return schema_is_candidate_complete(candidate)


def append_signal(candidate: dict, signal: str) -> None:
    """Добавляет signal кандидату без дублей."""
    signals = candidate.setdefault("signals", [])
    if signal not in signals:
        signals.append(signal)
