"""Watched list filter, sort and view helpers (no Qt)."""

from __future__ import annotations

from datetime import date

from desktop.watched.model.load import WatchedEntry
from dataset.models.media_type import (
    MOVIE_MEDIA_TYPE_ALIASES,
    TV_MEDIA_TYPE_ALIASES,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TV,
    normalize_media_type,
)

SORT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("user_score", "Моя оценка"),
    ("tmdb_score", "TMDb"),
    ("tmdb_votes", "Голоса TMDb"),
    ("tmdb_popularity", "Популярность TMDb"),
    ("year", "Год"),
    ("title", "Название"),
)

USER_SCORE_MIN = 1
USER_SCORE_MAX = 3
USER_SCORE_STEP = 1
YEAR_FILTER_MIN = 1980
YEAR_FILTER_MAX = date.today().year
YEAR_FILTER_DEFAULT_FROM = YEAR_FILTER_MIN
YEAR_FILTER_DEFAULT_TO = date.today().year

GENRE_FILTER_ALL = "Все жанры"

MEDIA_FILTER_OPTIONS: tuple[tuple[str, str | None], ...] = (
    ("watched.filters.media_all", None),
    ("watched.filters.media_tv", MEDIA_TYPE_TV),
    ("watched.filters.media_movie", MEDIA_TYPE_MOVIE),
)


def filter_by_title(entries: list[WatchedEntry], query: str) -> list[WatchedEntry]:
    """Return entries whose title matches the search query (case-insensitive)."""
    from desktop.shared.widgets.list_search import normalize_search_query

    normalized = normalize_search_query(query)
    if normalized == "":
        return list(entries)

    result: list[WatchedEntry] = []
    for key, movie, card in entries:
        title = (card.get("title") or key or "").casefold()
        if normalized in title or normalized in str(key).casefold():
            result.append((key, movie, card))
    return result


def _coerce_filter_score(value) -> int | None:
    from dataset.models.user_rating import normalize_user_rating

    return normalize_user_rating(value)


def filter_entries_by_user_score(
    entries: list[WatchedEntry],
    min_score: float | set[int] | tuple[int, ...] | list[int] | None = None,
    max_score: float | None = None,
) -> list[WatchedEntry]:
    """Return entries whose user_score is inside the inclusive range."""
    if isinstance(min_score, (set, tuple, list)):
        selected = {score for score in min_score if _coerce_filter_score(score) is not None}
        if not selected:
            return list(entries)
        return [entry for entry in entries if _coerce_filter_score(entry[2].get("user_score")) in selected]
    lower = USER_SCORE_MIN if min_score is None else float(min_score)
    upper = USER_SCORE_MAX if max_score is None else float(max_score)
    if lower > upper:
        lower, upper = upper, lower
    if lower <= USER_SCORE_MIN and upper >= USER_SCORE_MAX:
        return list(entries)

    result: list[WatchedEntry] = []
    for entry in entries:
        _key, _movie, card = entry
        score = _coerce_filter_score(card.get("user_score"))
        if score is None:
            continue
        if lower <= score <= upper:
            result.append(entry)
    return result


def _coerce_filter_year(value) -> int | None:
    if value is None:
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year


def _entry_year(entry: WatchedEntry) -> int | None:
    _key, movie, card = entry
    main_info = movie.get("main_info", {}) if isinstance(movie, dict) else {}
    if isinstance(main_info, dict):
        year = _coerce_filter_year(main_info.get("year"))
        if year is not None:
            return year
    return _coerce_filter_year(card.get("year"))


def filter_entries_by_year(
    entries: list[WatchedEntry],
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[WatchedEntry]:
    """Return entries whose main year is inside the inclusive range."""
    lower = YEAR_FILTER_MIN if year_from is None else int(year_from)
    upper = YEAR_FILTER_MAX if year_to is None else int(year_to)
    if lower > upper:
        lower, upper = upper, lower
    if lower <= YEAR_FILTER_MIN and upper >= YEAR_FILTER_MAX:
        return list(entries)

    result: list[WatchedEntry] = []
    for entry in entries:
        year = _entry_year(entry)
        if year is None:
            continue
        if lower <= year <= upper:
            result.append(entry)
    return result


def _entry_genres(entry: WatchedEntry) -> list[str]:
    _key, _movie, card = entry
    genres = card.get("genres") or []
    if isinstance(genres, str):
        genres = [genres]
    result: list[str] = []
    for genre in genres:
        text = str(genre).strip()
        if text:
            result.append(text)
    return result


def get_available_genres(entries: list[WatchedEntry]) -> list[str]:
    """Return sorted genre labels present in watched entries."""
    genres: set[str] = set()
    for entry in entries:
        genres.update(_entry_genres(entry))
    return sorted(genres, key=str.casefold)


def filter_entries_by_genre(entries: list[WatchedEntry], genre: str | None = None) -> list[WatchedEntry]:
    """Return entries containing the selected watched-card genre."""
    if genre is None:
        return list(entries)
    selected = str(genre).strip()
    if selected == "" or selected == GENRE_FILTER_ALL:
        return list(entries)

    result: list[WatchedEntry] = []
    for entry in entries:
        if selected in _entry_genres(entry):
            result.append(entry)
    return result


def normalize_media_type_filter(media_type: str | None) -> str | None:
    """Return a supported media_type filter value, or None for all titles."""
    if media_type in (None, ""):
        return None
    text = str(media_type).strip().casefold()
    if text in TV_MEDIA_TYPE_ALIASES:
        return MEDIA_TYPE_TV
    if text in MOVIE_MEDIA_TYPE_ALIASES:
        return MEDIA_TYPE_MOVIE
    return None


def _entry_media_type(entry: WatchedEntry) -> str:
    _key, movie, card = entry
    card_media_type = card.get("media_type") if isinstance(card, dict) else None
    if card_media_type not in (None, ""):
        return normalize_media_type(card_media_type)
    if isinstance(movie, dict):
        main_info = movie.get("main_info") if isinstance(movie.get("main_info"), dict) else {}
        media_type = main_info.get("media_type") or movie.get("media_type")
        return normalize_media_type(media_type)
    return normalize_media_type(None)


def filter_entries_by_media_type(
    entries: list[WatchedEntry],
    media_type: str | None = None,
) -> list[WatchedEntry]:
    """Return entries matching an explicit series/movie filter."""
    selected = normalize_media_type_filter(media_type)
    if selected is None:
        return list(entries)
    return [entry for entry in entries if _entry_media_type(entry) == selected]


def sort_entries(entries: list[WatchedEntry], sort_key: str) -> list[WatchedEntry]:
    """Return a sorted copy of entries without mutating source data."""
    items = list(entries)

    if sort_key == "title":
        return sorted(
            items,
            key=lambda entry: (entry[2].get("title") or entry[0] or "").lower(),
        )

    def numeric_sort_key(entry: WatchedEntry) -> tuple[int, float | int]:
        raw_value = entry[2].get(sort_key)
        if raw_value is None:
            return (1, 0)
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return (1, 0)
        if value.is_integer():
            value = int(value)
        if value is None:
            return (1, 0)
        return (0, value)

    return sorted(items, key=numeric_sort_key, reverse=True)


def apply_view(
    entries: list[WatchedEntry],
    query: str,
    sort_key: str,
    min_score: float | None = None,
    max_score: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    genre: str | None = None,
    media_type: str | None = None,
    title_index=None,
    user_ratings: set[int] | tuple[int, ...] | list[int] | None = None,
) -> list[WatchedEntry]:
    """Filter and sort entries for display."""
    if title_index is not None:
        filtered = title_index.filter_by_query(query)
    else:
        filtered = filter_by_title(entries, query)
    filtered = filter_entries_by_user_score(
        filtered,
        user_ratings if user_ratings is not None else min_score,
        max_score,
    )
    filtered = filter_entries_by_year(filtered, year_from, year_to)
    filtered = filter_entries_by_genre(filtered, genre)
    filtered = filter_entries_by_media_type(filtered, media_type)
    return sort_entries(filtered, sort_key)


def score_filter_is_active(min_score, max_score: float | None = None) -> bool:
    """Return True when at least one user reaction filter is selected."""
    if isinstance(min_score, (set, tuple, list)):
        return bool(min_score)
    upper = USER_SCORE_MAX if max_score is None else max_score
    lower = USER_SCORE_MIN if min_score is None else min_score
    return float(lower) > USER_SCORE_MIN or float(upper) < USER_SCORE_MAX


def year_filter_is_active(year_from: int, year_to: int) -> bool:
    """Return True when year range differs from the full supported range."""
    return int(year_from) != YEAR_FILTER_DEFAULT_FROM or int(year_to) != YEAR_FILTER_DEFAULT_TO


def genre_filter_is_active(genre: str | None) -> bool:
    """Return True when a specific genre is selected instead of all genres."""
    if genre is None:
        return False
    selected = str(genre).strip()
    return selected != "" and selected != GENRE_FILTER_ALL


def media_type_filter_is_active(media_type: str | None) -> bool:
    """Return True when series/movie filter is set to a specific type."""
    return normalize_media_type_filter(media_type) is not None


def watched_filters_are_active(
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
    has_media_type_filter: bool = False,
) -> bool:
    """Return True when at least one watched-list filter is active."""
    return bool(has_score_filter or has_year_filter or has_genre_filter or has_media_type_filter)


def watched_filters_are_active_from_ranges(
    min_score: float = USER_SCORE_MIN,
    max_score: float = USER_SCORE_MAX,
    year_from: int = YEAR_FILTER_DEFAULT_FROM,
    year_to: int = YEAR_FILTER_DEFAULT_TO,
    genre: str | None = None,
    media_type: str | None = None,
) -> bool:
    """Return True when any filter differs from defaults."""
    return (
        score_filter_is_active(min_score, max_score)
        or year_filter_is_active(year_from, year_to)
        or genre_filter_is_active(genre)
        or media_type_filter_is_active(media_type)
    )
