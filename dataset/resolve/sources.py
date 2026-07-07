"""TMDb source helpers for title resolve."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from apis import tmdb_api as api_tmdb
from candidates.sources.tmdb.normalizer import prepare_tmdb_candidate
from dataset.resolve.countries import country_value_to_iso2


def _tmdb_error(error: str, details: str) -> dict[str, Any]:
    return {"ok": False, "error": error, "details": details}


def _normalize_title(value) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def _year_from_item(item: dict[str, Any]) -> int | None:
    value = item.get("year") or item.get("first_air_date")
    if value in (None, ""):
        return None
    try:
        return int(str(value)[:4])
    except ValueError:
        return None


def _country_signals(item: dict[str, Any]) -> set[str]:
    signals = set()
    for value in item.get("origin_country") or []:
        text = str(value or "").strip().upper()
        if text:
            signals.add(text)
    return signals


def _query_title(query) -> str:
    if isinstance(query, dict):
        return str(query.get("title") or query.get("query") or "").strip()
    return str(query or "").strip()


def _query_year(query) -> int | None:
    if isinstance(query, dict) is False:
        return None
    value = query.get("year")
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _query_country(query) -> str | None:
    if isinstance(query, dict) is False:
        return None
    raw_value = str(query.get("country_code") or query.get("country") or "").strip()
    value = (country_value_to_iso2(raw_value) or raw_value).strip().upper()
    return value or None


def _unique_queries(queries: list) -> list:
    result = []
    seen = set()
    for query in queries or []:
        key = (
            _query_title(query).casefold(),
            _query_year(query),
            _query_country(query),
        )
        if key[0] == "" or key in seen:
            continue
        seen.add(key)
        result.append(query)
    return result


def _title_score(item: dict[str, Any], title: str) -> float:
    if title == "":
        return 0.0
    expected = _normalize_title(title)
    candidates = [
        _normalize_title(item.get("name")),
        _normalize_title(item.get("original_name")),
    ]
    return max((SequenceMatcher(None, expected, candidate).ratio() for candidate in candidates if candidate), default=0.0)


def choose_best_tmdb_result(
    results: list[dict[str, Any]],
    *,
    title: str = "",
    year: int | None = None,
    country: str | None = None,
) -> dict[str, Any] | None:
    """Choose the best TMDb search result using title/year/country when available."""
    if not results:
        return None

    country = str(country or "").upper()

    def score(item: dict[str, Any]) -> tuple:
        item_year = _year_from_item(item)
        year_score = 0
        if year is not None and item_year is not None:
            year_score = 2 if item_year == year else 1 if abs(item_year - year) <= 1 else -2

        country_score = 1 if country and country in _country_signals(item) else 0
        return (
            year_score,
            country_score,
            _title_score(item, title),
            item.get("vote_count") or 0,
            item.get("popularity") or 0,
        )

    return max(results, key=score)


def _normalizer_payload(raw_details: dict[str, Any], normalizer) -> dict[str, Any]:
    normalizer = normalizer or prepare_tmdb_candidate
    data = normalizer(raw_details)
    data = dict(data or {})
    if "genres_tmdb" not in data and isinstance(data.get("genres"), list):
        data["genres_tmdb"] = list(data["genres"])
    if "country_display" not in data and isinstance(data.get("countries"), list):
        data["country_display"] = ", ".join(str(value) for value in data["countries"] if str(value or "").strip())
    if data.get("source") in (None, ""):
        data["source"] = "tmdb"
    return data


def search_tmdb_defaults_data(
    queries: list,
    *,
    search_func=None,
    choose_func=None,
    details_func=None,
    normalizer=None,
    language: str | None = None,
) -> dict:
    """Search TMDb and return normalized add-flow data without KP/IMDb rating fields."""
    search_func = search_func or api_tmdb.search_tv_by_name
    details_func = details_func or api_tmdb.get_tv_details
    resolved_language = str(language or api_tmdb.DEFAULT_LANGUAGE).strip() or api_tmdb.DEFAULT_LANGUAGE
    last_error = None

    for query in _unique_queries(queries):
        title = _query_title(query)
        if title == "":
            continue

        try:
            try:
                results = search_func(title, language=resolved_language)
            except TypeError:
                results = search_func(title)
            choose = choose_func or choose_best_tmdb_result
            try:
                selected = choose(
                    results,
                    title=title,
                    year=_query_year(query),
                    country=_query_country(query),
                )
            except TypeError:
                selected = choose(results)
            if selected is None:
                last_error = _tmdb_error("not_found", f"TMDb не нашёл объект: {title}")
                continue

            try:
                details = details_func(
                    int(selected["id"]),
                    language=resolved_language,
                    append_to_response=api_tmdb.DEFAULT_TV_DETAIL_APPENDS,
                )
            except TypeError:
                details = details_func(
                    int(selected["id"]),
                    append_to_response=api_tmdb.DEFAULT_TV_DETAIL_APPENDS,
                )
            return {
                "data": _normalizer_payload(details, normalizer),
                "error": None,
                "status": "найдено",
            }
        except Exception as error:  # noqa: BLE001 - внешний API не должен ронять ручное добавление.
            last_error = _tmdb_error("network_error", str(error))

    if last_error is None:
        last_error = _tmdb_error("not_found", "TMDb не нашёл объект")
    return {
        "data": None,
        "error": last_error,
        "status": "не найдено" if last_error.get("error") == "not_found" else "ошибка",
    }
