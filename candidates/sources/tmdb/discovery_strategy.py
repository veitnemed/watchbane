"""Discovery slicing helpers for broader TMDb candidate pool collection."""

from __future__ import annotations

from typing import Any

from candidates.sources.tmdb.discover_query import normalize_country_code

DEFAULT_YEAR_WINDOW = 5
RU_ORIGINAL_LANGUAGE = "ru"


def _coerce_year(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _year_windows(year_min: int | None, year_max: int | None, *, window_size: int = DEFAULT_YEAR_WINDOW) -> list[tuple[int | None, int | None]]:
    start = _coerce_year(year_min)
    end = _coerce_year(year_max)
    if start is None and end is None:
        return [(None, None)]
    if start is None:
        return [(None, end)]
    if end is None:
        return [(start, None)]
    if start > end:
        start, end = end, start

    windows = []
    current = start
    while current <= end:
        window_end = min(current + window_size - 1, end)
        windows.append((current, window_end))
        current = window_end + 1
    return windows


def _normalize_genre_slices(with_genres) -> list[str | None]:
    text = str(with_genres or "").strip()
    if text == "":
        return [None]
    parts = [part.strip() for part in text.replace("|", ",").split(",")]
    genres = [part for part in parts if part]
    return genres or [text]


def _base_query(
    *,
    country: str,
    sort_by: str,
    year_start: int | None,
    year_end: int | None,
    without_genres,
    pages_per_slice: int,
    with_origin_country: str | None = None,
    with_original_language: str | None = None,
    with_genres: str | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {
        "country": country,
        "sort_by": sort_by,
        "max_pages": max(1, int(pages_per_slice)),
    }
    if with_origin_country:
        query["with_origin_country"] = with_origin_country
    if with_original_language:
        query["with_original_language"] = with_original_language
    if year_start is not None:
        query["first_air_date.gte"] = f"{year_start:04d}-01-01"
        query["year_min"] = year_start
    if year_end is not None:
        query["first_air_date.lte"] = f"{year_end:04d}-12-31"
        query["year_max"] = year_end
    if with_genres:
        query["with_genres"] = with_genres
    if without_genres:
        query["without_genres"] = without_genres
    return query


def _slice_name(*, source: str, sort_by: str, year_start: int | None, year_end: int | None, genre: str | None) -> str:
    parts = [source, sort_by.replace(".", "_")]
    if year_start is not None or year_end is not None:
        parts.append(f"{year_start or 'any'}_{year_end or 'any'}")
    if genre:
        parts.append(f"genre_{genre}")
    return "__".join(str(part) for part in parts)


def build_discovery_slices(
    country,
    year_min=None,
    year_max=None,
    with_genres=None,
    without_genres=None,
    pages_per_slice=2,
) -> list[dict]:
    country_code = normalize_country_code(country)
    year_windows = _year_windows(year_min, year_max)
    genre_slices = _normalize_genre_slices(with_genres)
    sources = [("origin_country", {"with_origin_country": country_code})]
    if country_code == "RU":
        sources.append(("original_language", {"with_original_language": RU_ORIGINAL_LANGUAGE}))
    sort_modes = ("vote_count.desc", "popularity.desc")

    slices: list[dict] = []
    seen_names: set[str] = set()
    for source_name, source_query in sources:
        for sort_by in sort_modes:
            for year_start, year_end in year_windows:
                for genre in genre_slices:
                    query = _base_query(
                        country=country_code,
                        sort_by=sort_by,
                        year_start=year_start,
                        year_end=year_end,
                        without_genres=without_genres,
                        pages_per_slice=pages_per_slice,
                        with_genres=genre,
                        **source_query,
                    )
                    name = _slice_name(
                        source=source_name,
                        sort_by=sort_by,
                        year_start=year_start,
                        year_end=year_end,
                        genre=genre,
                    )
                    if name in seen_names:
                        continue
                    seen_names.add(name)
                    slices.append({
                        "slice_name": name,
                        "query": query,
                        "pages_per_slice": max(1, int(pages_per_slice)),
                    })
    return slices


def _tmdb_id(item: dict[str, Any]) -> str | None:
    value = item.get("id", item.get("tmdb_id"))
    if value in (None, ""):
        return None
    return str(value)


def _result_rank(item: dict[str, Any]) -> tuple:
    return (
        int(item.get("vote_count") or 0),
        float(item.get("popularity") or 0),
    )


def _trace_entry(slice_name: str, query: dict[str, Any], page: int, original_order: int) -> dict[str, Any]:
    return {
        "slice_name": slice_name,
        "query": dict(query),
        "page": int(page),
        "original_order": int(original_order),
    }


def _iter_slice_results(results_by_slice):
    if isinstance(results_by_slice, dict):
        iterable = results_by_slice.values()
    else:
        iterable = results_by_slice or []

    for slice_index, slice_result in enumerate(iterable):
        if isinstance(slice_result, dict) is False:
            continue
        slice_name = str(slice_result.get("slice_name") or f"slice_{slice_index}")
        query = slice_result.get("query") if isinstance(slice_result.get("query"), dict) else {}
        page = int(slice_result.get("page") or 1)
        results = slice_result.get("results") or []
        for index, item in enumerate(results):
            if isinstance(item, dict):
                yield slice_name, query, page, index, item


def merge_discovery_results(results_by_slice) -> list[dict]:
    merged_by_id: dict[str, dict[str, Any]] = {}
    order_by_id: dict[str, int] = {}

    for global_order, (slice_name, query, page, original_order, item) in enumerate(_iter_slice_results(results_by_slice)):
        tmdb_id = _tmdb_id(item)
        if tmdb_id is None:
            continue
        trace = _trace_entry(slice_name, query, page, original_order)
        current = merged_by_id.get(tmdb_id)
        if current is None:
            merged = dict(item)
            merged["source_trace"] = [trace]
            merged_by_id[tmdb_id] = merged
            order_by_id[tmdb_id] = global_order
            continue

        current["source_trace"].append(trace)
        if _result_rank(item) > _result_rank(current):
            updated = dict(item)
            updated["source_trace"] = current["source_trace"]
            merged_by_id[tmdb_id] = updated

    return [
        merged_by_id[tmdb_id]
        for tmdb_id in sorted(order_by_id, key=lambda value: order_by_id[value])
    ]
