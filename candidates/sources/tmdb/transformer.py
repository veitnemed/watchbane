"""TMDb candidate transformation, enrichment, and scoring."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any

from candidates import kp_enrichment
from candidates.schema import normalize_candidate_record
from candidates.sources.tmdb.discover_query import normalize_country_code
from apis import imdb_sql as sql_search
from apis import tmdb_api as api_tmdb


ROOT_DIR = Path(__file__).resolve().parents[3]
KP_CACHE_DIR = ROOT_DIR / "data" / "cache" / "kp"
NETWORK_ERROR_SKIP_THRESHOLD = 3

SERIES_TITLE_TYPES = {"tvSeries", "tvMiniSeries"}
JUNK_IMDB_GENRES = {
    "Short",
    "Reality-TV",
    "Talk-Show",
    "Game-Show",
    "News",
    "Sport",
    "Adult",
}
CORE_IMDB_GENRES = {"Crime", "Drama", "Mystery"}
TMDB_TV_GENRE_NAMES_BY_ID = {
    10759: "Action & Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    10762: "Kids",
    9648: "Mystery",
    10763: "News",
    10764: "Reality",
    10765: "Sci-Fi & Fantasy",
    10766: "Soap",
    10767: "Talk",
    10768: "War & Politics",
    37: "Western",
}


def normalize_genre_name(name: str) -> str:
    return str(name or "").strip().casefold().replace("ё", "е")


def _genre_values_from_field(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, dict):
        value = [value]
    if isinstance(value, list) is False and isinstance(value, tuple) is False and isinstance(value, set) is False:
        return []

    genres = []
    for item in value:
        if isinstance(item, dict):
            genre_name = item.get("name") or item.get("genre") or item.get("title")
            if genre_name:
                genres.append(str(genre_name))
        elif item is not None:
            text = str(item).strip()
            if text:
                genres.append(text)
    return genres


def collect_candidate_genres(candidate: dict) -> set[str]:
    genres: set[str] = set()
    for field in ("genres", "imdb_genres", "genres_tmdb", "tmdb_genres"):
        for genre_name in _genre_values_from_field(candidate.get(field)):
            normalized = normalize_genre_name(genre_name)
            if normalized:
                genres.add(normalized)

    for genre_id in candidate.get("genre_ids") or []:
        try:
            genre_name = TMDB_TV_GENRE_NAMES_BY_ID.get(int(genre_id))
        except (TypeError, ValueError):
            genre_name = None
        normalized = normalize_genre_name(genre_name or "")
        if normalized:
            genres.add(normalized)

    return genres


def contains_cyrillic(text: str | None) -> bool:
    return any("\u0400" <= char <= "\u04FF" for char in str(text or ""))


def norm_name(value: str | None) -> str:
    return str(value or "").strip().casefold()


def append_signal(candidate: dict[str, Any], signal: str) -> None:
    signals = candidate.setdefault("signals", [])
    if signal not in signals:
        signals.append(signal)


_progress_reporter = None


def set_progress_reporter(reporter) -> None:
    """Регистрирует обработчик прогресса. Печать выполняет UI/CLI, не candidates."""
    global _progress_reporter
    _progress_reporter = reporter


def report_progress(source: str, status: str) -> None:
    """Сообщает шаг прогресса наверх; сам candidates ничего не печатает."""
    if _progress_reporter is not None:
        _progress_reporter(source, status)


def set_kp_status(candidate: dict[str, Any], status: str, is_complete: bool) -> None:
    candidate["kp_status"] = status
    candidate["is_complete"] = is_complete
    candidate.update(normalize_candidate_record(candidate))


def compute_country_score(candidate: dict[str, Any], target_country: str) -> tuple[float, list[str]]:
    target_country = normalize_country_code(target_country)
    score = 0.0
    signals: list[str] = []
    origin = {str(item).upper() for item in candidate.get("tmdb_origin_countries") or []}
    country_codes = {str(item).upper() for item in candidate.get("tmdb_country_codes") or []}
    production_countries = {norm_name(item) for item in candidate.get("tmdb_production_countries") or []}
    networks = {norm_name(item) for item in candidate.get("networks") or []}
    companies = {norm_name(item) for item in candidate.get("production_companies") or []}
    language = candidate.get("original_language")

    if target_country == "RU":
        if "RU" in origin:
            score += 0.50
            signals.append("origin_country_ru")
        if "RU" in country_codes or "russia" in production_countries or "russian federation" in production_countries:
            score += 0.45
            signals.append("production_country_russia")
        if language == "ru":
            score += 0.20
            signals.append("original_language_ru")
        if networks & {norm_name(item) for item in ["Kinopoisk", "Channel One", "Russia-1", "NTV", "START", "Premier"]}:
            score += 0.10
            signals.append("russian_network")
        if companies & {norm_name(item) for item in ["Sreda", "Kinopoisk", "Plus Studio", "Yellow Black and White", "1-2-3 Production"]}:
            score += 0.10
            signals.append("russian_production_company")
        if contains_cyrillic(candidate.get("title")) or contains_cyrillic(candidate.get("original_title")):
            score += 0.05
            signals.append("cyrillic_title")

    elif target_country == "KR":
        if "KR" in origin:
            score += 0.50
            signals.append("origin_country_kr")
        if "KR" in country_codes or "south korea" in production_countries or "korea, republic of" in production_countries:
            score += 0.45
            signals.append("production_country_south_korea")
        if language == "ko":
            score += 0.25
            signals.append("original_language_ko")
        if networks & {norm_name(item) for item in ["tvN", "Netflix", "SBS", "KBS2", "MBC", "JTBC", "OCN"]}:
            score += 0.10
            signals.append("korean_network")
    else:
        if target_country in origin:
            score += 0.55
            signals.append("origin_country_match")
        if target_country in country_codes:
            score += 0.45
            signals.append("production_country_code_match")

    return min(score, 1.0), signals


def connect_imdb(db_path: str | Path = sql_search.DEFAULT_DB_PATH) -> sqlite3.Connection | None:
    db_path = Path(db_path)
    if db_path.is_file() is False:
        return None
    conn = sql_search.connect_db(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _row_has_column(row: sqlite3.Row, column: str) -> bool:
    return column in row.keys()


def split_imdb_genres(raw_value) -> list[str]:
    genres = []
    for item in str(raw_value or "").split(","):
        genre = item.strip()
        if genre and genre != "\\N" and genre not in genres:
            genres.append(genre)
    return genres


def enrich_from_imdb_sql(candidate: dict[str, Any], conn: sqlite3.Connection | None) -> dict[str, Any]:
    imdb_id = candidate.get("imdb_id")
    if imdb_id in (None, ""):
        append_signal(candidate, "missing_imdb_id")
        return candidate
    if conn is None:
        append_signal(candidate, "imdb_sql_not_available")
        return candidate

    row = conn.execute("SELECT * FROM titles WHERE tconst = ?", (imdb_id,)).fetchone()
    if row is None:
        append_signal(candidate, "imdb_not_found_in_sql")
        return candidate

    candidate["imdb_found_in_sql"] = True
    candidate["imdb_title_type"] = row["titleType"]
    candidate["imdb_is_adult"] = row["isAdult"] if _row_has_column(row, "isAdult") else None
    candidate["imdb_start_year"] = row["startYear"]
    candidate["imdb_end_year"] = row["endYear"] if _row_has_column(row, "endYear") else None
    candidate["imdb_runtime_minutes"] = row["runtimeMinutes"] if _row_has_column(row, "runtimeMinutes") else None
    candidate["imdb_genres"] = split_imdb_genres(row["genres"])
    candidate["imdb_rating"] = row["averageRating"]
    candidate["imdb_votes"] = row["numVotes"]
    return candidate


def passes_imdb_filters(candidate: dict[str, Any]) -> tuple[bool, str | None]:
    if candidate.get("imdb_is_adult") == 1:
        return False, "adult"

    title_type = candidate.get("imdb_title_type")
    if title_type not in (None, "") and title_type not in SERIES_TITLE_TYPES:
        return False, "title_type"

    genres = set(candidate.get("imdb_genres") or [])
    if genres and genres <= JUNK_IMDB_GENRES:
        return False, "junk_genres_only"

    return True, None


def _rating_component(value: Any, floor: float = 5.5) -> float:
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min((rating - floor) / (10.0 - floor), 1.0))


def _log_votes_component(value: Any, target: int) -> float:
    try:
        votes = int(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if votes <= 0:
        return 0.0
    return min(math.log10(votes + 1) / math.log10(target + 1), 1.0)


def compute_quality_score(candidate: dict[str, Any]) -> float:
    tmdb_rating = candidate.get("tmdb_rating")
    tmdb_votes = candidate.get("tmdb_votes")
    imdb_rating = candidate.get("imdb_rating")
    imdb_votes = candidate.get("imdb_votes")

    score = 0.35 * _rating_component(tmdb_rating)
    score += 0.20 * _log_votes_component(tmdb_votes, 300)

    if imdb_rating not in (None, ""):
        score += 0.30 * _rating_component(imdb_rating)
        score += 0.15 * _log_votes_component(imdb_votes, 10_000)
    else:
        score *= 0.86
        append_signal(candidate, "quality_without_imdb")

    best_rating = max(float(tmdb_rating or 0), float(imdb_rating or 0))
    if best_rating and best_rating < 6.3:
        score *= 0.45
        append_signal(candidate, "low_rating_penalty")

    if int(tmdb_votes or 0) < 10 and imdb_rating in (None, ""):
        score *= 0.50
        append_signal(candidate, "low_votes_without_imdb")

    imdb_genres = set(candidate.get("imdb_genres") or [])
    tmdb_genres = set(candidate.get("genres_tmdb") or [])
    has_comedy = "Comedy" in imdb_genres or "Comedy" in tmdb_genres
    has_core = bool(imdb_genres & CORE_IMDB_GENRES) or bool(tmdb_genres & {"Crime", "Drama", "Mystery"})
    if has_comedy and not has_core:
        score *= 0.85
        append_signal(candidate, "comedy_only_penalty")

    return round(max(0.0, min(score, 1.0)), 4)


def compute_hidden_gem_score(candidate: dict[str, Any]) -> float:
    rating = max(float(candidate.get("tmdb_rating") or 0), float(candidate.get("imdb_rating") or 0))
    tmdb_votes = int(candidate.get("tmdb_votes") or 0)
    imdb_votes = int(candidate.get("imdb_votes") or 0)
    popularity = float(candidate.get("tmdb_popularity") or 0)

    if rating < 7.0:
        return 0.0

    score = _rating_component(rating, floor=6.5) * 0.40
    if 20 <= tmdb_votes <= 300:
        score += 0.25
    elif 10 <= tmdb_votes < 20 or 300 < tmdb_votes <= 800:
        score += 0.12

    if 500 <= imdb_votes <= 20_000:
        score += 0.25
    elif imdb_votes == 0:
        score += 0.05
    elif 100 <= imdb_votes < 500 or 20_000 < imdb_votes <= 60_000:
        score += 0.12

    if popularity <= 8:
        score += 0.10
    elif popularity <= 20:
        score += 0.05

    return round(max(0.0, min(score, 1.0)), 4)


def compute_final_score(candidate: dict[str, Any], mode: str = "quality") -> float:
    country_score = float(candidate.get("country_score") or 0)
    quality_score = float(candidate.get("quality_score") or 0)
    hidden_gem_score = float(candidate.get("hidden_gem_score") or 0)
    if mode == "hidden_gems":
        score = 0.35 * country_score + 0.45 * quality_score + 0.20 * hidden_gem_score
    else:
        score = 0.30 * country_score + 0.70 * quality_score
    return round(max(0.0, min(score, 1.0)), 4)


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def unique_non_empty(values: list[Any]) -> list[Any]:
    return kp_enrichment.unique_non_empty(values)


def tmdb_country_to_kp_country(country: str) -> str:
    return kp_enrichment.kp_country_from_iso2(country)


def candidate_year(candidate: dict[str, Any]) -> int | None:
    return kp_enrichment.candidate_year(candidate)


def kp_api_description(movie: dict[str, Any]) -> str:
    return kp_enrichment.kp_api_description(movie)


def kp_match_is_safe(candidate: dict[str, Any], movie: dict[str, Any]) -> tuple[bool, str | None]:
    return kp_enrichment.kp_match_is_safe(candidate, movie)


def fill_candidate_from_kp_api(candidate: dict[str, Any], movie: dict[str, Any]) -> None:
    kp_enrichment.fill_candidate_from_kp_api(candidate, movie)


def mark_kp_pending_limit(candidate: dict[str, Any]) -> dict[str, Any]:
    set_kp_status(candidate, "pending_limit", False)
    append_signal(candidate, "kp_pending_limit")
    return candidate


def enrich_from_kp_api_if_needed(
    candidate: dict[str, Any],
    country: str,
    stats: dict[str, Any],
    *,
    skip_network: bool = False,
    kp_debug_session=None,
) -> dict[str, Any]:
    """Дополняет TMDb-кандидата KP API, если cache не дал KP-рейтинг/голоса."""
    if candidate.get("kp_rating") not in (None, "") and candidate.get("kp_votes") not in (None, ""):
        set_kp_status(candidate, "cache_hit", True)
        stats["kp_api_skipped_cache"] += 1
        report_progress("KP API", "Cache hit")
        return candidate

    if skip_network:
        stats["kp_api_skipped_after_errors"] += 1
        set_kp_status(candidate, "skipped_network_errors", False)
        append_signal(candidate, "kp_api_skipped_after_network_errors")
        report_progress("KP API", "Пропущено")
        return candidate

    kp_country = tmdb_country_to_kp_country(country)
    queries = kp_enrichment.candidate_kp_queries(candidate)
    if len(queries) == 0:
        stats["kp_api_not_found"] += 1
        set_kp_status(candidate, "not_requested", False)
        append_signal(candidate, "kp_api_no_query")
        report_progress("KP API", "Нет кандидатов")
        return candidate

    report_progress("KP API", "Ожидание ответа")
    if kp_debug_session is not None:
        kp_debug_session.start_candidate(candidate, kp_country)
    lookup = kp_enrichment.lookup_kp_via_api(
        candidate,
        queries,
        kp_country,
        continue_on_reject=False,
        attempt_traces=kp_debug_session.current_attempts if kp_debug_session is not None else None,
    )
    if kp_debug_session is not None:
        kp_debug_session.finish_candidate(candidate, lookup)
    stats["kp_api_requested"] += int(lookup.get("attempts") or 0)

    if lookup["status"] == "found":
        fill_candidate_from_kp_api(candidate, lookup["movie"] or {})
        stats["kp_api_found"] += 1
        set_kp_status(candidate, "done", True)
        append_signal(candidate, "kp_api_hit")
        report_progress("KP API", "Успешно")
        return candidate

    if lookup["status"] == "error":
        error_code = lookup.get("error") or "unknown"
        stats["kp_api_errors"] += 1
        set_kp_status(candidate, "error", False)
        append_signal(candidate, "kp_api_error")
        append_signal(candidate, f"kp_api_error_{error_code}")
        report_progress("KP API", "Ошибка сети")
        return candidate

    if lookup["status"] == "rejected":
        reason = lookup.get("reject_reason") or "unknown"
        stats["kp_api_rejected_by_match"] += 1
        set_kp_status(candidate, "not_found", False)
        append_signal(candidate, f"kp_api_rejected_{reason}")
        report_progress("KP API", "Отклонено match-check")
        return candidate

    stats["kp_api_not_found"] += 1
    set_kp_status(candidate, "not_found", False)
    append_signal(candidate, "kp_api_not_found")
    report_progress("KP API", "Нет кандидатов")
    return candidate


def normalize_tmdb_candidate_for_common_pool(candidate: dict[str, Any], criteria_name=None) -> dict[str, Any]:
    """Добавляет common candidate fields к TMDb v1 кандидату, не удаляя исходные поля."""
    normalized = dict(candidate)
    imdb_genres = candidate.get("imdb_genres") or []
    tmdb_genres = candidate.get("genres_tmdb") or []
    countries = unique_non_empty(
        list(candidate.get("tmdb_origin_countries") or [])
        + list(candidate.get("tmdb_production_countries") or [])
        + list(candidate.get("tmdb_country_codes") or [])
    )

    normalized.update({
        "title": candidate.get("title"),
        "original_title": candidate.get("original_title"),
        "year": safe_int(candidate.get("year")),
        "tmdb_id": safe_int(candidate.get("tmdb_id")),
        "imdb_id": candidate.get("imdb_id"),
        "kp_id": candidate.get("kp_id"),
        "tmdb_score": safe_float(candidate.get("tmdb_rating")),
        "tmdb_votes": safe_int(candidate.get("tmdb_votes")),
        "imdb_score": safe_float(candidate.get("imdb_rating")),
        "imdb_votes": safe_int(candidate.get("imdb_votes")),
        "kp_score": safe_float(candidate.get("kp_rating")),
        "kp_votes": safe_int(candidate.get("kp_votes")),
        "genres": unique_non_empty(list(imdb_genres) + list(tmdb_genres)),
        "countries": countries,
        "description": candidate.get("overview") or "",
        "source": "tmdb_imdb_kp_v1",
        "criteria_name": criteria_name,
        "kp_status": candidate.get("kp_status") or "not_requested",
        "is_complete": bool(candidate.get("is_complete")),
    })
    return normalize_candidate_record(normalized)


def enrich_from_kp_cache_only(candidate: dict[str, Any]) -> dict[str, Any]:
    for key in [candidate.get("tmdb_id"), candidate.get("imdb_id")]:
        if key in (None, ""):
            continue
        path = KP_CACHE_DIR / f"{key}.json"
        if path.is_file():
            with open(path, "r", encoding="utf-8") as file:
                cached = json.load(file)
            candidate["kp_id"] = cached.get("kp_id") or cached.get("id")
            candidate["kp_rating"] = cached.get("kp_rating") or cached.get("rating")
            candidate["kp_votes"] = cached.get("kp_votes") or cached.get("votes")
            set_kp_status(candidate, "cache_hit", True)
            append_signal(candidate, "kp_cache_hit")
            return candidate

    candidate["kp_id"] = None
    candidate["kp_rating"] = None
    candidate["kp_votes"] = None
    set_kp_status(candidate, "not_requested", False)
    return candidate


def prepare_candidate(raw_details: dict[str, Any], country: str, source_query: dict[str, Any]) -> dict[str, Any]:
    candidate = api_tmdb.normalize_tmdb_tv(raw_details)
    candidate["source_query"] = source_query
    country_score, country_signals = compute_country_score(candidate, country)
    candidate["country_score"] = country_score
    candidate["country_signals"] = country_signals
    return candidate
