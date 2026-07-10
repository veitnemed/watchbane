"""Shared helpers for watched analytics."""

from __future__ import annotations

from pathlib import Path

from config import constant

from dataset.analytics.scores import normalize_score


def _movie_section(movie: dict, key: str) -> dict:
    section = movie.get(key)
    return section if isinstance(section, dict) else {}


def _clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text != "" else None


def _has_rating_value(value) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _genres_from_movie(movie: dict) -> list[str]:
    for field_name in ("genres_display", "genre_display", "genres", "imdb_genres", "genres_tmdb", "tmdb_genres"):
        value = movie.get(field_name)
        if isinstance(value, list):
            genres = [_clean_text(item) for item in value]
            genres = [genre for genre in genres if genre is not None]
            if genres:
                return genres
        text = _clean_text(value)
        if text is not None:
            return [text]

    genre_section = _movie_section(movie, constant.GENRE_SECTION)
    labels = constant.FIELD_LABELS
    result: list[str] = []
    for feature in constant.GENRE:
        if genre_section.get(feature) != 1:
            continue
        label = _clean_text(labels.get(feature))
        if label is None:
            label = feature.removeprefix("has_").replace("_", " ").title()
        if label not in result:
            result.append(label)
    return result


def _overview_from_movie(movie: dict) -> str | None:
    for field_name in ("overview", "description", "short_description", "shortDescription", "plot"):
        for section in (movie, _movie_section(movie, "main_info")):
            text = _clean_text(section.get(field_name))
            if text is not None:
                return text
    return None


def _poster_fields_from_movie(movie: dict) -> dict:
    poster = _movie_section(movie, "poster")
    poster_url = _clean_text(movie.get("poster_url") or movie.get("posterUrl") or poster.get("url"))
    poster_path = _clean_text(movie.get("poster_path") or movie.get("posterPath") or poster.get("path"))
    poster_src = poster_path or poster_url
    return {
        "poster_url": poster_url,
        "poster_path": poster_path,
        "poster_src": poster_src,
    }


def completeness_card_from_movie(movie: dict) -> dict:
    main_info = _movie_section(movie, "main_info")
    raw_scores = _movie_section(movie, "raw_scores")
    poster_fields = _poster_fields_from_movie(movie)
    return {
        "user_score": main_info.get("user_score", movie.get("user_score")),
        "year": main_info.get("year", movie.get("year")),
        "genres": _genres_from_movie(movie),
        "tmdb_score": raw_scores.get("tmdb_score", movie.get("tmdb_score")),
        "overview": _overview_from_movie(movie),
        **poster_fields,
    }


def external_score(value) -> float | None:
    if not _has_rating_value(value):
        return None
    return normalize_score(value)


def normalize_analytics_entries(entries: list[tuple[str, dict, dict]]) -> list[tuple[str, dict, dict]]:
    normalized: list[tuple[str, dict, dict]] = []
    for entry in entries:
        if isinstance(entry, tuple) and len(entry) == 3:
            key, movie, card = entry
            if isinstance(movie, dict):
                normalized.append((str(key), movie, card if isinstance(card, dict) else {}))
    return normalized


def collect_analytics_entry_items(entries: list[tuple[str, dict, dict]]) -> list[dict]:
    """Build normalized read-only analytics rows from watched GUI entries."""
    items: list[dict] = []
    for key, movie, card in normalize_analytics_entries(entries):
        display = card if card else completeness_card_from_movie(movie)
        title = _clean_text(display.get("title")) or str(key)
        genres = display.get("genres")
        if genres is None:
            genres = _genres_from_movie(movie)
        if isinstance(genres, str):
            genre_values = [genres] if genres.strip() else []
        else:
            genre_values = [_clean_text(genre) for genre in genres]
        genre_values = [genre for genre in genre_values if genre is not None]

        overview = display.get("overview", _overview_from_movie(movie))
        items.append(
            {
                "title": title,
                "year": display.get("year", _movie_section(movie, "main_info").get("year", movie.get("year"))),
                "user_score": normalize_score(
                    display.get("user_score", _movie_section(movie, "main_info").get("user_score", movie.get("user_score")))
                ),
                "genres": genre_values,
                "tmdb_score": external_score(
                    display.get("tmdb_score", _movie_section(movie, "raw_scores").get("tmdb_score", movie.get("tmdb_score")))
                ),
                "has_overview": overview not in (None, "") and bool(str(overview).strip()),
            }
        )
    return items
