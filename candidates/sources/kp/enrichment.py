"""Shared KP API match/fill helpers for TMDb build and common pool retry."""

from __future__ import annotations

from typing import Any, Callable

from apis import kp_api


# Labels match candidates.tmdb_country_options.COUNTRY_NAMES_RU_BY_CODE (TMDb build UI).
KR_COUNTRY_ALIASES = (
    "Южная Корея",
    "Корея Южная",
    "Республика Корея",
    "South Korea",
    "Republic of Korea",
    "Korea, Republic of",
    "KR",
)

KP_COUNTRY_BY_ISO2 = {
    "RU": "Россия",
    "US": "США",
    "GB": "Великобритания",
    "KR": "Южная Корея",
    "JP": "Япония",
    "FR": "Франция",
    "DE": "Германия",
    "ES": "Испания",
    "IT": "Италия",
    "TR": "Турция",
    "CN": "Китай",
    "IN": "Индия",
    "CA": "Канада",
    "AU": "Австралия",
    "BR": "Бразилия",
    "MX": "Мексика",
    "AR": "Аргентина",
    "SE": "Швеция",
    "NO": "Норвегия",
    "DK": "Дания",
    "FI": "Финляндия",
    "PL": "Польша",
    "NL": "Нидерланды",
    "BE": "Бельгия",
    "IE": "Ирландия",
    "UA": "Украина",
}

_COUNTRY_ALIAS_TO_CANONICAL: dict[str, str] = {}


def _normalize_country_key(value: str) -> str:
    text = str(value or "").strip().casefold().replace("ё", "е")
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


def _register_country_aliases(canonical: str, *aliases: str) -> None:
    for alias in aliases:
        key = _normalize_country_key(alias)
        if key:
            _COUNTRY_ALIAS_TO_CANONICAL[key] = canonical


def _init_country_alias_map() -> None:
    for iso2, ru_name in KP_COUNTRY_BY_ISO2.items():
        _register_country_aliases(iso2, iso2, ru_name)
    _register_country_aliases("KR", *KR_COUNTRY_ALIASES)


_init_country_alias_map()


def normalize_country_alias(value: str) -> str:
    """Maps a country label/code to canonical ISO-2 when alias is known."""
    key = _normalize_country_key(value)
    if key == "":
        return ""
    return _COUNTRY_ALIAS_TO_CANONICAL.get(key, key)


def extract_kp_country_values(source: Any) -> list[str]:
    """Reads country labels from KP API shapes: str, list, dict(name/country), movie.countries."""
    if source is None:
        return []
    if isinstance(source, str):
        text = source.strip()
        return [text] if text else []
    if isinstance(source, list):
        values: list[str] = []
        for item in source:
            values.extend(extract_kp_country_values(item))
        return unique_non_empty(values)
    if isinstance(source, dict):
        if "countries" in source:
            return extract_kp_country_values(source.get("countries"))
        values: list[str] = []
        for field in ("name", "country"):
            raw = source.get(field)
            if isinstance(raw, str) and raw.strip():
                values.append(raw.strip())
            elif isinstance(raw, list):
                values.extend(extract_kp_country_values(raw))
        return unique_non_empty(values)
    return []


def countries_match(expected_country: str, kp_country_values: list[str]) -> bool:
    """Returns True when expected country matches any KP country label via explicit aliases."""
    expected = str(expected_country or "").strip()
    if expected == "" or len(kp_country_values) == 0:
        return False

    expected_canonical = normalize_country_alias(expected)
    expected_key = _normalize_country_key(expected)
    for kp_value in kp_country_values:
        kp_canonical = normalize_country_alias(str(kp_value))
        if kp_canonical == expected_canonical:
            return True
        if _normalize_country_key(str(kp_value)) == expected_key:
            return True
    return False


def normalize_iso2_country(value: str | None) -> str:
    return str(value or "").strip().upper()


def kp_country_from_iso2(country: str) -> str:
    """Maps ISO-2 country code to KP API country label."""
    return KP_COUNTRY_BY_ISO2.get(normalize_iso2_country(country), "")


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def unique_non_empty(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if value in (None, ""):
            continue
        key = str(value).strip()
        if key == "" or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def candidate_year(candidate: dict[str, Any]) -> int | None:
    return safe_int(candidate.get("year") or candidate.get("imdb_start_year"))


def candidate_kp_queries(candidate: dict[str, Any], *, include_alternative_title: bool = False) -> list[Any]:
    fields = ["title", "original_title"]
    if include_alternative_title:
        fields.append("alternative_title")
    return unique_non_empty([candidate.get(field_name) for field_name in fields])


def kp_api_description(movie: dict[str, Any]) -> str:
    return str(movie.get("description") or movie.get("shortDescription") or "").strip()


def kp_match_is_safe(candidate: dict[str, Any], movie: dict[str, Any]) -> tuple[bool, str | None]:
    if kp_api.is_series(movie) is False:
        return False, "not_series"

    candidate_titles = unique_non_empty([
        candidate.get("title"),
        candidate.get("original_title"),
    ])
    title_score = 0.0
    for title in candidate_titles:
        title_score = max(title_score, kp_api.title_match_score(str(title), movie))
    if title_score < 0.78:
        return False, "title_mismatch"

    expected_year = candidate_year(candidate)
    kp_year = safe_int(movie.get("year"))
    if expected_year is not None and kp_year is not None and abs(kp_year - expected_year) > 1:
        return False, "year_mismatch"

    return True, None


def fill_candidate_from_kp_api(candidate: dict[str, Any], movie: dict[str, Any]) -> None:
    kp_rating = kp_api.safe_nested(movie, "rating", "kp")
    kp_votes = kp_api.safe_nested(movie, "votes", "kp")
    if movie.get("id") not in (None, ""):
        candidate["kp_id"] = movie.get("id")
    if kp_rating not in (None, ""):
        candidate["kp_rating"] = kp_rating
    if kp_votes not in (None, ""):
        candidate["kp_votes"] = kp_votes

    description = kp_api_description(movie)
    if description and not str(candidate.get("overview") or "").strip():
        candidate["overview"] = description
    if movie.get("name"):
        candidate["kp_title"] = movie.get("name")


def lookup_kp_via_api(
    candidate: dict[str, Any],
    queries: list[Any],
    country: str,
    *,
    find_series_raw: Callable[..., dict[str, Any]] | None = None,
    continue_on_reject: bool = False,
    attempt_traces: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Looks up KP data for candidate queries and applies shared match-check."""
    find_series_raw = find_series_raw or kp_api.find_series_raw
    year = candidate_year(candidate)
    last_error = None
    last_reject = None

    if len(queries) == 0:
        return {
            "status": "no_query",
            "movie": None,
            "error": "empty_query",
            "reject_reason": None,
            "query": None,
            "attempts": 0,
        }

    attempts = 0
    for query in queries:
        attempts += 1
        attempt_trace = None
        query_finder = find_series_raw
        if attempt_traces is not None:
            from candidates.sources.tmdb import debug as kp_tmdb_build_debug

            attempt_trace = kp_tmdb_build_debug.new_attempt_record(candidate, str(query), country, year)
            query_finder = kp_tmdb_build_debug.make_tracing_find_series_raw(attempt_trace)

        result = query_finder(str(query), country, year=year)
        if result.get("ok") is False:
            error_code = result.get("error") or "unknown"
            if attempt_trace is not None:
                attempt_trace["lookup_status"] = "api_error"
                attempt_traces.append(attempt_trace)
            if error_code in {"not_found", "country_not_found", "empty_title"}:
                last_error = error_code
                continue
            return {
                "status": "error",
                "movie": None,
                "error": error_code,
                "reject_reason": None,
                "query": str(query),
                "attempts": attempts,
            }

        movie = result.get("data") or {}
        is_safe, reason = kp_match_is_safe(candidate, movie)
        if attempt_trace is not None:
            from candidates.sources.tmdb import debug as kp_tmdb_build_debug

            lookup_status = "found" if is_safe else "rejected"
            kp_tmdb_build_debug.fill_match_trace(
                attempt_trace,
                candidate,
                movie,
                is_safe,
                reason,
                lookup_status=lookup_status,
            )
            attempt_traces.append(attempt_trace)

        if is_safe is False:
            last_reject = reason
            last_error = f"rejected_{reason}"
            if continue_on_reject:
                continue
            return {
                "status": "rejected",
                "movie": None,
                "error": last_error,
                "reject_reason": reason,
                "query": str(query),
                "attempts": attempts,
            }

        return {
            "status": "found",
            "movie": movie,
            "error": None,
            "reject_reason": None,
            "query": str(query),
            "attempts": attempts,
        }

    return {
        "status": "not_found",
        "movie": None,
        "error": last_error or "not_found",
        "reject_reason": last_reject,
        "query": None,
        "attempts": attempts,
    }
