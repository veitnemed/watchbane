"""Watched list filter, sort and view helpers (no Qt)."""

from __future__ import annotations

from datetime import date

from desktop.watched.model.load import WatchedEntry

SORT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("user_score", "Моя оценка"),
    ("year", "Год"),
    ("imdb_score", "IMDb"),
    ("kp_score", "КП"),
    ("title", "Название"),
)

USER_SCORE_MIN = 0.0
USER_SCORE_MAX = 10.0
USER_SCORE_STEP = 0.1
YEAR_FILTER_MIN = 1980
YEAR_FILTER_MAX = date.today().year
YEAR_FILTER_DEFAULT_FROM = 2000
YEAR_FILTER_DEFAULT_TO = date.today().year

GENRE_FILTER_ALL = "Все жанры"


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


def _coerce_filter_score(value) -> float | None:
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < USER_SCORE_MIN or score > USER_SCORE_MAX:
        return None
    return score


def filter_entries_by_user_score(
    entries: list[WatchedEntry],
    min_score: float | None = None,
    max_score: float | None = None,
) -> list[WatchedEntry]:
    """Return entries whose user_score is inside the inclusive range."""
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


def apply_view(
    entries: list[WatchedEntry],
    query: str,
    sort_key: str,
    min_score: float | None = None,
    max_score: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    genre: str | None = None,
    title_index=None,
) -> list[WatchedEntry]:
    """Filter and sort entries for display."""
    if title_index is not None:
        filtered = title_index.filter_by_query(query)
    else:
        filtered = filter_by_title(entries, query)
    filtered = filter_entries_by_user_score(filtered, min_score, max_score)
    filtered = filter_entries_by_year(filtered, year_from, year_to)
    filtered = filter_entries_by_genre(filtered, genre)
    return sort_entries(filtered, sort_key)


def score_filter_is_active(min_score: float, max_score: float) -> bool:
    """Return True when user score range differs from the default 0.0–10.0."""
    return float(min_score) > USER_SCORE_MIN or float(max_score) < USER_SCORE_MAX


def year_filter_is_active(year_from: int, year_to: int) -> bool:
    """Return True when year range differs from the default 2000–current year."""
    return int(year_from) != YEAR_FILTER_DEFAULT_FROM or int(year_to) != YEAR_FILTER_DEFAULT_TO


def genre_filter_is_active(genre: str | None) -> bool:
    """Return True when a specific genre is selected instead of all genres."""
    if genre is None:
        return False
    selected = str(genre).strip()
    return selected != "" and selected != GENRE_FILTER_ALL


def watched_filters_are_active(
    has_score_filter: bool = False,
    has_year_filter: bool = False,
    has_genre_filter: bool = False,
) -> bool:
    """Return True when at least one score/year/genre filter is active."""
    return bool(has_score_filter or has_year_filter or has_genre_filter)


def watched_filters_are_active_from_ranges(
    min_score: float = USER_SCORE_MIN,
    max_score: float = USER_SCORE_MAX,
    year_from: int = YEAR_FILTER_DEFAULT_FROM,
    year_to: int = YEAR_FILTER_DEFAULT_TO,
    genre: str | None = None,
) -> bool:
    """Return True when any filter range/genre differs from defaults."""
    return (
        score_filter_is_active(min_score, max_score)
        or year_filter_is_active(year_from, year_to)
        or genre_filter_is_active(genre)
    )
