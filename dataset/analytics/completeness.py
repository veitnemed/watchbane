"""Watched dataset field completeness analytics."""

from __future__ import annotations

from pathlib import Path

from dataset.analytics.helpers import (
    _clean_text,
    _genres_from_movie,
    _has_rating_value,
    _movie_section,
    _overview_from_movie,
    _poster_fields_from_movie,
    completeness_card_from_movie,
)
from dataset.analytics.scores import normalize_score

DATASET_COMPLETENESS_FIELDS: tuple[tuple[str, str], ...] = (
    ("user_score", "Мои оценки"),
    ("year", "Годы"),
    ("genres", "Жанры"),
    ("imdb", "IMDb"),
    ("kp", "КП"),
    ("description", "Описания"),
    ("poster", "Постеры"),
)

DATASET_COMPLETENESS_DISPLAY_KEYS: tuple[str, ...] = (
    "poster",
    "description",
    "imdb",
    "kp",
    "genres",
    "year",
)

DATASET_COMPLETENESS_WORST_LIMIT = 4


def _entry_has_user_score(movie: dict, card: dict) -> bool:
    score = card.get("user_score", _movie_section(movie, "main_info").get("user_score", movie.get("user_score")))
    return normalize_score(score) is not None


def _entry_has_year(movie: dict, card: dict) -> bool:
    year = card.get("year", _movie_section(movie, "main_info").get("year", movie.get("year")))
    if year in (None, ""):
        return False
    try:
        return int(year) > 0
    except (TypeError, ValueError):
        return False


def _entry_has_genres(movie: dict, card: dict) -> bool:
    genres = card.get("genres")
    if genres is None:
        genres = _genres_from_movie(movie)
    if isinstance(genres, str):
        return bool(genres.strip())
    if isinstance(genres, list):
        return any(_clean_text(genre) is not None for genre in genres)
    return False


def _entry_has_imdb(movie: dict, card: dict) -> bool:
    value = card.get("imdb_score", _movie_section(movie, "raw_scores").get("imdb_score", movie.get("imdb_score")))
    return _has_rating_value(value)


def _entry_has_kp(movie: dict, card: dict) -> bool:
    value = card.get("kp_score", _movie_section(movie, "raw_scores").get("kp_score", movie.get("kp_score")))
    return _has_rating_value(value)


def _entry_has_description(movie: dict, card: dict) -> bool:
    overview = card.get("overview", _overview_from_movie(movie))
    return overview not in (None, "") and bool(str(overview).strip())


def _entry_has_poster(movie: dict, card: dict) -> bool:
    fields = {
        "poster_url": card.get("poster_url"),
        "poster_path": card.get("poster_path"),
        "poster_src": card.get("poster_src"),
    }
    if all(value in (None, "") for value in fields.values()):
        fields = _poster_fields_from_movie(movie)

    poster_url = _clean_text(fields.get("poster_url"))
    if poster_url is not None:
        return True

    for field_name in ("poster_src", "poster_path"):
        value = _clean_text(fields.get(field_name))
        if value is None:
            continue
        if value.startswith(("http://", "https://")):
            return True
        if Path(value).is_file():
            return True
    return False


_DATASET_COMPLETENESS_CHECKS = {
    "user_score": _entry_has_user_score,
    "year": _entry_has_year,
    "genres": _entry_has_genres,
    "imdb": _entry_has_imdb,
    "kp": _entry_has_kp,
    "description": _entry_has_description,
    "poster": _entry_has_poster,
}


def _build_dataset_completeness_payload(entries: list[tuple[str, dict, dict]]) -> dict:
    total = len(entries)
    counts = {key: 0 for key, _label in DATASET_COMPLETENESS_FIELDS}
    for _key, movie, card in entries:
        if isinstance(movie, dict) is False:
            continue
        display_card = card if isinstance(card, dict) else completeness_card_from_movie(movie)
        for field_key, checker in _DATASET_COMPLETENESS_CHECKS.items():
            if checker(movie, display_card):
                counts[field_key] += 1

    items: list[dict] = []
    percents: list[float] = []
    for field_key, label in DATASET_COMPLETENESS_FIELDS:
        count = counts[field_key]
        percent = 0.0 if total == 0 else round(count * 100 / total, 1)
        percents.append(percent)
        items.append(
            {
                "key": field_key,
                "label": label,
                "count": count,
                "total": total,
                "percent": percent,
            }
        )

    overall_percent = 0.0 if len(percents) == 0 else round(sum(percents) / len(percents), 1)
    return {
        "total": total,
        "overall_percent": overall_percent,
        "items": items,
    }


def build_dataset_completeness_from_entries(entries: list[tuple[str, dict, dict]]) -> dict:
    """Build watched dataset completeness stats from GUI entries."""
    normalized: list[tuple[str, dict, dict]] = []
    for entry in entries:
        if isinstance(entry, tuple) and len(entry) == 3:
            key, movie, card = entry
            if isinstance(movie, dict):
                normalized.append((str(key), movie, card if isinstance(card, dict) else {}))
    return _build_dataset_completeness_payload(normalized)


def build_dataset_completeness(records) -> dict:
    """Build watched dataset completeness stats from raw dataset records."""
    if isinstance(records, dict):
        iterable = records.items()
    else:
        iterable = enumerate(records)

    entries: list[tuple[str, dict, dict]] = []
    for key, movie in iterable:
        if isinstance(movie, dict) is False:
            continue
        entries.append((str(key), movie, completeness_card_from_movie(movie)))
    return _build_dataset_completeness_payload(entries)


def summarize_dataset_completeness(completeness: dict) -> dict:
    """Build compact read-only summary lines from precomputed completeness data."""
    total = int(completeness.get("total") or 0)
    overall_percent = float(completeness.get("overall_percent") or 0.0)
    items = [item for item in completeness.get("items", []) if isinstance(item, dict)]
    headline_text = f"Полнота dataset: {overall_percent:.0f}%"

    if total == 0:
        return {
            "overall_percent": 0.0,
            "worst_items": [],
            "headline_text": headline_text,
            "subline_text": "Нет записей в watched-базе.",
        }

    incomplete = [item for item in items if float(item.get("percent") or 0) < 100.0]
    incomplete.sort(
        key=lambda item: (float(item.get("percent") or 0), str(item.get("key") or "")),
    )
    worst_items = incomplete[:DATASET_COMPLETENESS_WORST_LIMIT]

    if len(worst_items) == 0:
        subline_text = "База почти полная."
    else:
        parts = [f"{item['label']} {item['count']}/{item['total']}" for item in worst_items]
        subline_text = "Нужно заполнить: " + " · ".join(parts)

    return {
        "overall_percent": overall_percent,
        "worst_items": worst_items,
        "headline_text": headline_text,
        "subline_text": subline_text,
    }
