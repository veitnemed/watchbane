"""Read-only helpers for the desktop watched-movies view."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from storage import data as storage_data
from web.export import build_export_lookup_cache, build_watched_movie_card

_poster_cache = None
_lookup_cache = None


def _get_poster_cache() -> dict:
    global _poster_cache
    if _poster_cache is None:
        try:
            from posters.cache import load_poster_cache

            _poster_cache = load_poster_cache()
        except Exception:
            _poster_cache = {}
    return _poster_cache


def _get_lookup_cache() -> dict:
    global _lookup_cache
    if _lookup_cache is None:
        _lookup_cache = build_export_lookup_cache()
    return _lookup_cache

WatchedEntry = tuple[str, dict, dict]

SORT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("user_score", "Моя оценка"),
    ("year", "Год"),
    ("imdb_score", "IMDb"),
    ("kp_score", "КП"),
    ("title", "Название"),
)


def load_watched_entries() -> list[WatchedEntry]:
    """Load dataset and return (dataset_key, movie, card) tuples."""
    data = storage_data.load_dataset()
    poster_cache = _get_poster_cache()
    lookup_cache = _get_lookup_cache()
    return [
        (key, movie, build_watched_movie_card(movie, poster_cache=poster_cache, lookup_cache=lookup_cache))
        for key, movie in data.items()
    ]


def prepare_card_for_display(movie: dict) -> dict:
    """Build a card dict for GUI display without mutating the source movie."""
    original = deepcopy(movie)
    card = build_watched_movie_card(
        movie,
        poster_cache=_get_poster_cache(),
        lookup_cache=_get_lookup_cache(),
    )
    if movie != original:
        raise RuntimeError("build_watched_movie_card mutated the source movie")
    return card


def filter_by_title(entries: list[WatchedEntry], query: str) -> list[WatchedEntry]:
    """Return entries whose title matches the search query (case-insensitive)."""
    normalized = query.strip().lower()
    if normalized == "":
        return list(entries)

    result: list[WatchedEntry] = []
    for key, movie, card in entries:
        title = (card.get("title") or key or "").lower()
        if normalized in title or normalized in key.lower():
            result.append((key, movie, card))
    return result


def sort_entries(entries: list[WatchedEntry], sort_key: str) -> list[WatchedEntry]:
    """Return a sorted copy of entries without mutating source data."""
    items = list(entries)

    if sort_key == "title":
        return sorted(
            items,
            key=lambda entry: (entry[2].get("title") or entry[0] or "").lower(),
        )

    def numeric_sort_key(entry: WatchedEntry) -> tuple[int, float | int]:
        value = entry[2].get(sort_key)
        if value is None:
            return (1, 0)
        return (0, value)

    return sorted(items, key=numeric_sort_key, reverse=True)


def apply_view(entries: list[WatchedEntry], query: str, sort_key: str) -> list[WatchedEntry]:
    """Filter and sort entries for display."""
    return sort_entries(filter_by_title(entries, query), sort_key)


def format_list_label(card: dict) -> str:
    """Compact label for the left-hand list."""
    title = card.get("title") or "Без названия"
    year = card.get("year")
    score = card.get("user_score")
    parts = [title]
    if year is not None:
        parts.append(f"({year})")
    label = " ".join(parts)
    if score is not None:
        label = f"{label}  ·  {score:g}"
    return label


def resolve_local_poster_path(movie: dict, card: dict | None = None) -> str | None:
    """Return a local filesystem poster path when available. Never uses network."""
    display_card = card if card is not None else build_watched_movie_card(movie)
    candidates: list[str | None] = [
        display_card.get("poster_path"),
        _local_path(display_card.get("poster_src")),
        _local_path(movie.get("poster_src")),
        _local_path(movie.get("poster_path")),
        _local_path(_nested_poster_value(movie, "path")),
        _local_path(_nested_poster_value(movie, "poster_path")),
    ]

    for candidate in candidates:
        if candidate is None:
            continue
        path = Path(candidate)
        if path.is_file():
            return str(path)
    return None


def _local_path(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.startswith(("http://", "https://")):
        return None
    return text


def _nested_poster_value(movie: dict, field: str) -> str | None:
    poster = movie.get("poster")
    if isinstance(poster, dict):
        return poster.get(field)
    return None
