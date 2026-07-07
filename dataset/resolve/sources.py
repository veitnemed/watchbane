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


_CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def _transliterate_cyrillic_query(value: str) -> str:
    result = []
    for char in str(value or ""):
        lower = char.casefold()
        mapped = _CYRILLIC_TO_LATIN.get(lower)
        if mapped is None:
            result.append(char)
        elif char.isupper() and mapped:
            result.append(mapped[:1].upper() + mapped[1:])
        else:
            result.append(mapped)
    return "".join(result).strip()


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


def _tmdb_search_titles(title: str) -> tuple[str, ...]:
    title = str(title or "").strip()
    transliterated = _transliterate_cyrillic_query(title)
    if transliterated and transliterated.casefold() != title.casefold():
        return (title, transliterated)
    return (title,)


def _title_score(item: dict[str, Any], title: str) -> float:
    if title == "":
        return 0.0
    expected_values = [_normalize_title(title)]
    transliterated = _transliterate_cyrillic_query(title)
    if transliterated and transliterated.casefold() != str(title or "").casefold():
        expected_values.append(_normalize_title(transliterated))
    candidates = [
        _normalize_title(item.get("name")),
        _normalize_title(item.get("original_name")),
    ]
    return max(
        (
            SequenceMatcher(None, expected, candidate).ratio()
            for expected in expected_values
            if expected
            for candidate in candidates
            if candidate
        ),
        default=0.0,
    )


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


def _normalizer_payload(
    raw_details: dict[str, Any],
    normalizer,
    *,
    language: str | None = None,
) -> dict[str, Any]:
    normalizer = normalizer or prepare_tmdb_candidate
    source_query = {"language": language} if language not in (None, "") else {}
    try:
        data = normalizer(raw_details, source_query=source_query)
    except TypeError:
        data = normalizer(raw_details)
    data = dict(data or {})
    if source_query:
        current_source_query = data.get("source_query")
        if isinstance(current_source_query, dict):
            data["source_query"] = {**current_source_query, **source_query}
        else:
            data["source_query"] = dict(source_query)
    if "genres_tmdb" not in data and isinstance(data.get("genres"), list):
        data["genres_tmdb"] = list(data["genres"])
    if "country_display" not in data and isinstance(data.get("countries"), list):
        data["country_display"] = ", ".join(str(value) for value in data["countries"] if str(value or "").strip())
    if data.get("source") in (None, ""):
        data["source"] = "tmdb"
    return data


def _tmdb_search_languages(language: str) -> tuple[str, ...]:
    primary = str(language or api_tmdb.DEFAULT_LANGUAGE).strip() or api_tmdb.DEFAULT_LANGUAGE
    fallback = api_tmdb.DEFAULT_LANGUAGE
    if primary == fallback:
        return (primary,)
    return (primary, fallback)


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

        for search_title in _tmdb_search_titles(title):
            for search_language in _tmdb_search_languages(resolved_language):
                try:
                    try:
                        results = search_func(search_title, language=search_language)
                    except TypeError:
                        results = search_func(search_title)
                    choose = choose_func or choose_best_tmdb_result
                    try:
                        selected = choose(
                            results,
                            title=search_title,
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
                        "data": _normalizer_payload(
                            details,
                            normalizer,
                            language=resolved_language,
                        ),
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
