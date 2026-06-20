"""Builds TMDb + local IMDb SQL candidate pools for TV recommendations."""

from __future__ import annotations

import csv
import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from candidates import candidate_pool as legacy_candidate_pool
from apis import imdb_sql as sql_search
from apis import kp_api
from apis import tmdb_api as api_tmdb


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "data" / "candidate_pool"
DIAGNOSTICS_DIR = ROOT_DIR / "data" / "diagnostics"
KP_CACHE_DIR = ROOT_DIR / "data" / "cache" / "kp"

SERIOUS_GENRES_TMDB = [18, 80, 9648]
WITHOUT_GENRES_TMDB = [16, 10751, 10762, 10763, 10764, 10767]
DEFAULT_VOTE_AVERAGE_GTE = 6.3
DEFAULT_VOTE_COUNT_GTE = 10
CSV_FIELDS = [
    "final_score",
    "country_score",
    "quality_score",
    "hidden_gem_score",
    "title",
    "original_title",
    "year",
    "tmdb_rating",
    "tmdb_score",
    "tmdb_votes",
    "imdb_rating",
    "imdb_score",
    "imdb_votes",
    "kp_score",
    "kp_status",
    "is_complete",
    "genres_tmdb",
    "imdb_genres",
    "original_language",
    "production_countries",
    "networks",
    "imdb_id",
    "tmdb_id",
    "country_signals",
    "overview",
    "description",
]
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
KP_COUNTRY_BY_ISO2 = {
    "RU": "Россия",
    "KR": "Южная Корея",
    "US": "США",
    "GB": "Великобритания",
    "DE": "Германия",
}
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


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def ensure_diagnostics_dir(output_dir: str | Path | None = None) -> Path:
    path = Path(output_dir) if output_dir is not None else DIAGNOSTICS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_tmdb_criteria_name(
    country: str,
    mode: str,
    year_min: int | None = None,
    min_tmdb_score: float | None = None,
) -> str:
    name = f"tmdb_{normalize_country_code(country)}_{mode}"
    if year_min is not None:
        name += f"_{int(year_min)}plus"
    if min_tmdb_score is not None:
        score = f"{float(min_tmdb_score):g}".replace(".", "_")
        name += f"_min{score}"
    return name


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


def normalize_country_code(value: str | None) -> str:
    return str(value or "").strip().upper()


def is_iso2_country_code(value: str | None) -> bool:
    code = normalize_country_code(value)
    return len(code) == 2 and code.isascii() and code.isalpha()


def discover_defaults(country: str) -> dict[str, Any]:
    country = normalize_country_code(country)
    params: dict[str, Any] = {
        "country": country,
        "genres_any": SERIOUS_GENRES_TMDB,
        "without_genres": WITHOUT_GENRES_TMDB,
        "vote_average_gte": DEFAULT_VOTE_AVERAGE_GTE,
        "vote_count_gte": DEFAULT_VOTE_COUNT_GTE,
        "language": "ru-RU",
        "sort_by": "vote_count.desc",
    }
    if country == "KR":
        params["with_original_language"] = "ko"
    return params


def apply_discover_filters(
    query: dict[str, Any],
    *,
    year_min: int | None = None,
    year_max: int | None = None,
    min_tmdb_score: float | None = None,
    min_tmdb_votes: int | None = None,
) -> dict[str, Any]:
    updated = dict(query)
    if year_min is not None:
        updated["year_min"] = int(year_min)
    if year_max is not None:
        updated["year_max"] = int(year_max)
    if min_tmdb_score is not None:
        updated["vote_average_gte"] = float(min_tmdb_score)
    if min_tmdb_votes is not None:
        updated["vote_count_gte"] = int(min_tmdb_votes)
    return updated


def deduplicate_discover_results(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    duplicates = 0
    for item in items:
        tmdb_id = item.get("id")
        if tmdb_id in (None, ""):
            continue
        tmdb_id = int(tmdb_id)
        if tmdb_id in seen:
            duplicates += 1
            continue
        seen.add(tmdb_id)
        unique.append(item)
    return unique, duplicates


def sort_discover_for_details(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            -(item.get("vote_count") or 0),
            -(item.get("vote_average") or 0),
            -(item.get("popularity") or 0),
            item.get("id") or 0,
        ),
    )


def remove_watched_discover(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    try:
        watched_signatures = legacy_candidate_pool.build_watched_signatures()
    except Exception:
        watched_signatures = set()

    if not watched_signatures:
        return items, 0

    filtered: list[dict[str, Any]] = []
    skipped = 0
    for item in items:
        candidate = {
            "title": item.get("name") or item.get("original_name") or "",
            "alternative_title": item.get("original_name") or "",
            "year": api_tmdb.get_year(item.get("first_air_date")),
        }
        if legacy_candidate_pool.is_watched_candidate(candidate, watched_signatures):
            skipped += 1
            continue
        filtered.append(item)
    return filtered, skipped


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


def tmdb_country_to_kp_country(country: str) -> str:
    return KP_COUNTRY_BY_ISO2.get(normalize_country_code(country), "")


def candidate_year(candidate: dict[str, Any]) -> int | None:
    return safe_int(candidate.get("year") or candidate.get("imdb_start_year"))


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


def mark_kp_pending_limit(candidate: dict[str, Any]) -> dict[str, Any]:
    set_kp_status(candidate, "pending_limit", False)
    append_signal(candidate, "kp_pending_limit")
    return candidate


def enrich_from_kp_api_if_needed(candidate: dict[str, Any], country: str, stats: dict[str, Any]) -> dict[str, Any]:
    """Дополняет TMDb-кандидата KP API, если cache не дал KP-рейтинг/голоса."""
    if candidate.get("kp_rating") not in (None, "") and candidate.get("kp_votes") not in (None, ""):
        set_kp_status(candidate, "cache_hit", True)
        stats["kp_api_skipped_cache"] += 1
        report_progress("KP API", "Cache hit")
        return candidate

    kp_country = tmdb_country_to_kp_country(country)
    queries = unique_non_empty([candidate.get("title"), candidate.get("original_title")])
    year = candidate_year(candidate)
    if len(queries) == 0:
        stats["kp_api_not_found"] += 1
        set_kp_status(candidate, "not_requested", False)
        append_signal(candidate, "kp_api_no_query")
        report_progress("KP API", "Нет кандидатов")
        return candidate

    last_error = None
    for query in queries:
        stats["kp_api_requested"] += 1
        report_progress("KP API", "Ожидание ответа")
        result = kp_api.find_series_raw(str(query), kp_country, year=year)
        if result.get("ok") is False:
            error_code = result.get("error")
            if error_code in {"not_found", "country_not_found", "empty_title"}:
                last_error = error_code
                continue
            stats["kp_api_errors"] += 1
            set_kp_status(candidate, "error", False)
            append_signal(candidate, "kp_api_error")
            append_signal(candidate, f"kp_api_error_{error_code or 'unknown'}")
            report_progress("KP API", "Ошибка сети")
            return candidate

        movie = result.get("data") or {}
        is_safe, reason = kp_match_is_safe(candidate, movie)
        if is_safe is False:
            stats["kp_api_rejected_by_match"] += 1
            set_kp_status(candidate, "not_found", False)
            append_signal(candidate, f"kp_api_rejected_{reason}")
            report_progress("KP API", "Отклонено match-check")
            return candidate

        fill_candidate_from_kp_api(candidate, movie)
        stats["kp_api_found"] += 1
        set_kp_status(candidate, "done", True)
        append_signal(candidate, "kp_api_hit")
        report_progress("KP API", "Успешно")
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
    return normalized


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


def build_candidate_pool(
    country: str,
    pages: int = 3,
    details_limit: int = 50,
    mode: str = "quality",
    criteria_name: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    min_tmdb_score: float | None = None,
    min_tmdb_votes: int | None = None,
    force_refresh: bool = False,
    db_path: str | Path = sql_search.DEFAULT_DB_PATH,
    kp_api_limit: int | None = None,
) -> dict[str, Any]:
    country = normalize_country_code(country)
    if is_iso2_country_code(country) is False:
        raise ValueError("country must be a 2-letter ISO code")
    if mode not in {"quality", "hidden_gems"}:
        raise ValueError("mode должен быть quality или hidden_gems")
    criteria_name = str(criteria_name or "").strip() or build_tmdb_criteria_name(
        country,
        mode,
        year_min=year_min,
        min_tmdb_score=min_tmdb_score,
    )

    token = api_tmdb.load_tmdb_token()
    query = apply_discover_filters(
        discover_defaults(country),
        year_min=year_min,
        year_max=year_max,
        min_tmdb_score=min_tmdb_score,
        min_tmdb_votes=min_tmdb_votes,
    )
    report_progress("TMDb Discover", "Ожидание ответа")
    try:
        discover_results = api_tmdb.discover_tv_candidates(
            max_pages=pages,
            force_refresh=force_refresh,
            token=token,
            **query,
        )
    except Exception:
        report_progress("TMDb Discover", "Ошибка сети")
        raise
    report_progress("TMDb Discover", f"Успешно, кандидатов: {len(discover_results)}")
    unique_results, duplicates_removed = deduplicate_discover_results(discover_results)
    not_watched_results, watched_skipped = remove_watched_discover(unique_results)
    sorted_results = sort_discover_for_details(not_watched_results)
    details_candidates = sorted_results[: int(details_limit)]

    conn = connect_imdb(db_path)
    candidates: list[dict[str, Any]] = []
    stats = {
        "discover_total": len(discover_results),
        "discover_filters": {
            "year_min": year_min,
            "year_max": year_max,
            "min_tmdb_score": min_tmdb_score,
            "min_tmdb_votes": min_tmdb_votes,
        },
        "duplicates_removed": duplicates_removed,
        "watched_skipped": watched_skipped,
        "details_requested": len(details_candidates),
        "has_imdb_id": 0,
        "found_in_imdb_sql": 0,
        "country_passed": 0,
        "country_borderline": 0,
        "country_rejected": 0,
        "imdb_filter_rejected": 0,
        "adult_title_type_rejected": 0,
        "kp_cache_hit": 0,
        "kp_api_requested": 0,
        "kp_api_found": 0,
        "kp_api_not_found": 0,
        "kp_api_rejected_by_match": 0,
        "kp_api_errors": 0,
        "kp_api_skipped_cache": 0,
        "kp_pending_limit": 0,
        "kp_incomplete_candidates": 0,
        "complete_candidates": 0,
        "final_candidates": 0,
    }

    try:
        for item in details_candidates:
            detail_index = len(candidates) + stats["country_rejected"] + stats["imdb_filter_rejected"] + 1
            report_progress("TMDb Details", f"Ожидание ответа [{detail_index}/{len(details_candidates)}]")
            try:
                details = api_tmdb.get_tv_details(
                    int(item["id"]),
                    language=query["language"],
                    force_refresh=force_refresh,
                    token=token,
                )
            except Exception:
                report_progress("TMDb Details", "Ошибка сети")
                raise
            report_progress("TMDb Details", f"Успешно [{detail_index}/{len(details_candidates)}]")
            candidate = prepare_candidate(details, country, source_query=query)
            if candidate.get("imdb_id"):
                stats["has_imdb_id"] += 1
            report_progress("IMDb dataset", f"Поиск [{detail_index}/{len(details_candidates)}]")
            candidate = enrich_from_imdb_sql(candidate, conn)
            if candidate.get("imdb_found_in_sql"):
                stats["found_in_imdb_sql"] += 1
                report_progress("IMDb dataset", f"Успешно [{detail_index}/{len(details_candidates)}]")
            else:
                report_progress("IMDb dataset", f"Нет кандидатов [{detail_index}/{len(details_candidates)}]")
            candidate = enrich_from_kp_cache_only(candidate)
            if "kp_cache_hit" in candidate.get("signals", []):
                stats["kp_cache_hit"] += 1
            if candidate.get("kp_status") == "cache_hit":
                candidate = enrich_from_kp_api_if_needed(candidate, country, stats)
            elif kp_api_limit is not None and stats["kp_api_requested"] >= int(kp_api_limit):
                candidate = mark_kp_pending_limit(candidate)
                report_progress("KP API", "Лимит, добрать позже")
            else:
                candidate = enrich_from_kp_api_if_needed(candidate, country, stats)

            if candidate["country_score"] >= 0.70:
                stats["country_passed"] += 1
            elif candidate["country_score"] >= 0.40:
                stats["country_borderline"] += 1
                append_signal(candidate, "borderline_country_score")
            else:
                stats["country_rejected"] += 1
                continue

            passes, reason = passes_imdb_filters(candidate)
            if passes is False:
                stats["imdb_filter_rejected"] += 1
                if reason in {"adult", "title_type"}:
                    stats["adult_title_type_rejected"] += 1
                append_signal(candidate, f"rejected_{reason}")
                continue

            candidate["quality_score"] = compute_quality_score(candidate)
            candidate["hidden_gem_score"] = compute_hidden_gem_score(candidate)
            candidate["final_score"] = compute_final_score(candidate, mode)
            candidates.append(normalize_tmdb_candidate_for_common_pool(candidate, criteria_name=criteria_name))
    finally:
        if conn is not None:
            conn.close()

    candidates.sort(
        key=lambda candidate: (
            -(candidate.get("final_score") or 0),
            -(candidate.get("quality_score") or 0),
            -(candidate.get("tmdb_votes") or 0),
            candidate.get("title") or "",
        )
    )
    stats["final_candidates"] = len(candidates)
    stats["kp_pending_limit"] = sum(1 for candidate in candidates if candidate.get("kp_status") == "pending_limit")
    stats["kp_incomplete_candidates"] = sum(1 for candidate in candidates if candidate.get("is_complete") is not True)
    stats["complete_candidates"] = sum(1 for candidate in candidates if candidate.get("is_complete") is True)

    return {
        "criteria_name": criteria_name,
        "country": country,
        "mode": mode,
        "source": "tmdb_discover_imdb_sql",
        "query": query,
        "settings": {
            "criteria_name": criteria_name,
            "country": country,
            "mode": mode,
            "pages": int(pages),
            "details_limit": int(details_limit),
            "year_min": year_min,
            "year_max": year_max,
            "min_tmdb_score": min_tmdb_score,
            "min_tmdb_votes": min_tmdb_votes,
        },
        "stats": stats,
        "candidates": candidates,
    }


def output_base_path(country: str, mode: str) -> Path:
    ensure_output_dir()
    return OUTPUT_DIR / f"candidate_pool_{country.upper()}_{mode}"


def save_candidate_pool_result(result: dict[str, Any]) -> tuple[Path, Path]:
    country = result["country"]
    mode = result["mode"]
    base_path = output_base_path(country, mode)
    json_path = base_path.with_suffix(".json")
    csv_path = base_path.with_suffix(".csv")

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in result["candidates"]:
            writer.writerow(candidate_to_csv_row(candidate))

    return json_path, csv_path


def save_candidate_pool_test_result(result: dict[str, Any]) -> tuple[Path, Path]:
    country = result["country"]
    mode = result["mode"]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ensure_output_dir()
    base_path = OUTPUT_DIR / f"test_candidate_pool_{country.upper()}_{mode}_{timestamp}"
    json_path = base_path.with_suffix(".json")
    csv_path = base_path.with_suffix(".csv")

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in result["candidates"]:
            writer.writerow(candidate_to_csv_row(candidate))

    return json_path, csv_path


def list_tmdb_result_files() -> list[Path]:
    ensure_output_dir()
    files = [
        path for path in OUTPUT_DIR.glob("*candidate_pool_*.json")
        if path.is_file()
    ]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files


def normalize_tmdb_candidate_for_common_import(candidate: dict[str, Any], criteria_name: str) -> dict[str, Any]:
    return {
        "id": candidate.get("kp_id"),
        "title": candidate.get("title"),
        "alternative_title": candidate.get("original_title"),
        "year": candidate.get("year"),
        "type": candidate.get("type") or "series",
        "description": candidate.get("description") or candidate.get("overview") or "",
        "kp_score": candidate.get("kp_score") if candidate.get("kp_score") is not None else candidate.get("kp_rating"),
        "kp_votes": candidate.get("kp_votes"),
        "imdb_score": candidate.get("imdb_score") if candidate.get("imdb_score") is not None else candidate.get("imdb_rating"),
        "imdb_votes": candidate.get("imdb_votes"),
        "countries": candidate.get("countries") or candidate.get("tmdb_origin_countries") or [],
        "genres": candidate.get("genres") or candidate.get("imdb_genres") or candidate.get("genres_tmdb") or [],
        "criteria_name": criteria_name,
        "source": "tmdb_imdb_kp_v1",
        "tmdb_id": candidate.get("tmdb_id"),
        "imdb_id": candidate.get("imdb_id"),
        "kp_id": candidate.get("kp_id"),
        "tmdb_score": candidate.get("tmdb_score") if candidate.get("tmdb_score") is not None else candidate.get("tmdb_rating"),
        "tmdb_votes": candidate.get("tmdb_votes"),
        "kp_status": candidate.get("kp_status"),
        "is_complete": candidate.get("is_complete"),
        "signals": candidate.get("signals") or [],
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }


def tmdb_import_default_criteria_name(result: dict[str, Any]) -> str | None:
    for value in [
        result.get("criteria_name"),
        (result.get("settings") or {}).get("criteria_name") if isinstance(result.get("settings"), dict) else None,
    ]:
        text = str(value or "").strip()
        if text:
            return text
    for candidate in result.get("candidates") or []:
        value = str(candidate.get("criteria_name") or "").strip()
        if value:
            return value
    country = str(result.get("country") or "").strip()
    mode = str(result.get("mode") or "").strip()
    if country and mode:
        return f"tmdb_{country}_{mode}"
    return None


def import_tmdb_result_to_common_pool(result_path, criteria_name: str | None = None) -> dict[str, Any]:
    result_path = Path(result_path)
    try:
        with open(result_path, "r", encoding="utf-8-sig") as file:
            result = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        return {
            "ok": False,
            "error": str(error),
            "read": 0,
            "added": 0,
            "updated": 0,
            "watched_skipped": 0,
            "duplicates": 0,
            "errors": 1,
        }

    candidates = result.get("candidates") if isinstance(result, dict) else None
    if isinstance(candidates, list) is False:
        return {
            "ok": False,
            "error": "В файле нет списка candidates.",
            "read": 0,
            "added": 0,
            "updated": 0,
            "watched_skipped": 0,
            "duplicates": 0,
            "errors": 1,
        }

    criteria_name = str(criteria_name or tmdb_import_default_criteria_name(result) or "").strip()
    if criteria_name == "":
        return {
            "ok": False,
            "error": "Не задан criteria_name.",
            "read": len(candidates),
            "added": 0,
            "updated": 0,
            "watched_skipped": 0,
            "duplicates": 0,
            "errors": 1,
        }

    pool = legacy_candidate_pool.load_candidate_pool()
    watched_signatures = legacy_candidate_pool.build_watched_signatures()
    stats = {
        "ok": True,
        "error": None,
        "read": len(candidates),
        "added": 0,
        "updated": 0,
        "watched_skipped": 0,
        "duplicates": 0,
        "errors": 0,
        "criteria_name": criteria_name,
        "source": "tmdb_imdb_kp_v1",
    }

    for raw_candidate in candidates:
        if isinstance(raw_candidate, dict) is False:
            stats["errors"] += 1
            continue

        candidate = normalize_tmdb_candidate_for_common_import(raw_candidate, criteria_name)
        if not candidate.get("title") or not candidate.get("year"):
            stats["errors"] += 1
            continue

        if legacy_candidate_pool.is_watched_candidate(candidate, watched_signatures):
            stats["watched_skipped"] += 1
            continue

        matched_key = None
        matched_candidate = None
        for key, existing_candidate in pool.items():
            if legacy_candidate_pool.candidates_are_same(candidate, existing_candidate, include_criteria=True):
                matched_key = key
                matched_candidate = existing_candidate
                break

        if matched_key is None:
            pool[legacy_candidate_pool.candidate_key(candidate)] = candidate
            stats["added"] += 1
            continue

        if legacy_candidate_pool.candidate_sort_score(candidate) > legacy_candidate_pool.candidate_sort_score(matched_candidate):
            pool[matched_key] = candidate
            stats["updated"] += 1
        else:
            stats["duplicates"] += 1

    legacy_candidate_pool.save_named_criteria(criteria_name, {
        "country": result.get("country"),
        "count": len(candidates),
        "min_kp": None,
        "min_imdb": None,
        "min_kp_votes": None,
        "min_imdb_votes": None,
        "min_year": None,
        "max_year": None,
        "genres": [],
        "excluded_genres": [],
        "source": "tmdb_imdb_kp_v1",
        "settings": result.get("settings") or {},
        "result_file": str(result_path),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    })
    legacy_candidate_pool.save_candidate_pool(pool)
    stats["pool_size"] = len(legacy_candidate_pool.load_candidate_pool())
    return stats


def _safe_year(value) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _find_nested_value(data, key: str):
    if isinstance(data, dict) is False:
        return None
    if key in data and data[key] not in (None, ""):
        return data[key]
    for value in data.values():
        if isinstance(value, dict):
            found = _find_nested_value(value, key)
            if found not in (None, ""):
                return found
        elif isinstance(value, list):
            for item in value:
                found = _find_nested_value(item, key)
                if found not in (None, ""):
                    return found
    return None


def _tmdb_id_from_meta(meta_obj: dict | None):
    if isinstance(meta_obj, dict) is False:
        return None
    return (
        meta_obj.get("tmdb_id")
        or _find_nested_value(meta_obj.get("tmdb_data"), "tmdb_id")
        or _find_nested_value(meta_obj.get("tmdb_data"), "id")
        or _find_nested_value(meta_obj.get("source_values"), "tmdb_id")
    )


def _genres_from_tmdb_details(details: dict[str, Any]) -> list[str]:
    if isinstance(details, dict) is False:
        return []
    if "genres_tmdb" in details:
        return unique_non_empty(_genre_values_from_field(details.get("genres_tmdb")))
    return unique_non_empty(api_tmdb.normalize_tmdb_tv(details).get("genres_tmdb") or [])


def build_tmdb_genre_distribution_report(
    dataset: dict,
    meta: dict | None = None,
    *,
    details_fetcher=None,
    search_func=None,
    choose_func=None,
    normalizer=None,
    progress_callback=None,
    max_consecutive_errors: int | None = 3,
) -> dict[str, Any]:
    details_fetcher = details_fetcher or api_tmdb.get_tv_details
    search_func = search_func or api_tmdb.search_tv_by_name
    choose_func = choose_func or api_tmdb.choose_best_result
    normalizer = normalizer or api_tmdb.normalize_tmdb_tv
    meta = meta or {}

    created_at = datetime.now().isoformat(timespec="seconds")
    genre_counts: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    unmatched_items: list[dict[str, Any]] = []
    empty_genre_items: list[dict[str, Any]] = []
    consecutive_errors = 0
    stopped_early = False
    stop_reason = None

    dataset_items = list((dataset or {}).items())
    total_items = len(dataset_items)
    for index, (title, record) in enumerate(dataset_items, start=1):
        main_info = record.get("main_info") if isinstance(record, dict) else {}
        title_text = str((main_info or {}).get("title") or title or "").strip()
        year = _safe_year((main_info or {}).get("year"))
        meta_obj = meta.get(title) or meta.get(title_text) or {}
        tmdb_id = _tmdb_id_from_meta(meta_obj)
        matched = False
        genres: list[str] = []
        error = None
        if progress_callback is not None:
            progress_callback({
                "index": index,
                "total": total_items,
                "title": title_text,
                "year": year,
                "status": "start",
                "tmdb_id": safe_int(tmdb_id),
                "genres": [],
            })

        try:
            if tmdb_id in (None, ""):
                results = search_func(title_text)
                selected = choose_func(results)
                if selected:
                    tmdb_id = selected.get("id")

            if tmdb_id not in (None, ""):
                details = details_fetcher(int(tmdb_id))
                normalized_details = normalizer(details)
                genres = unique_non_empty(
                    normalized_details.get("genres_tmdb")
                    or _genres_from_tmdb_details(details)
                )
                matched = True
        except Exception as exc:
            error = str(exc)
            matched = False

        item = {
            "title": title_text,
            "year": year,
            "tmdb_id": safe_int(tmdb_id),
            "matched": matched,
            "genres": genres,
        }
        if error:
            item["error"] = error
        items.append(item)

        if matched:
            consecutive_errors = 0
            if len(genres) == 0:
                empty_genre_items.append({"title": title_text, "year": year, "tmdb_id": safe_int(tmdb_id)})
            for genre_name in genres:
                genre_counts[genre_name] = genre_counts.get(genre_name, 0) + 1
        else:
            unmatched_items.append({"title": title_text, "year": year})
            if error:
                consecutive_errors += 1
            else:
                consecutive_errors = 0

        if progress_callback is not None:
            status = "matched" if matched else "unmatched"
            if error:
                status = "error"
            progress_callback({
                "index": index,
                "total": total_items,
                "title": title_text,
                "year": year,
                "status": status,
                "tmdb_id": safe_int(tmdb_id),
                "genres": genres,
                "error": error,
            })

        if (
            max_consecutive_errors is not None
            and max_consecutive_errors > 0
            and consecutive_errors >= max_consecutive_errors
        ):
            stopped_early = True
            stop_reason = f"Остановлено после {consecutive_errors} подряд ошибок TMDb: {error}"
            if progress_callback is not None:
                progress_callback({
                    "index": index,
                    "total": total_items,
                    "title": title_text,
                    "year": year,
                    "status": "stopped",
                    "error": stop_reason,
                    "processed": len(items),
                })
            break

    genre_counts = dict(sorted(genre_counts.items(), key=lambda pair: (-pair[1], pair[0])))
    return {
        "created_at": created_at,
        "source": "dataset",
        "total_dataset_items": len(dataset or {}),
        "matched": sum(1 for item in items if item["matched"]),
        "unmatched": len(unmatched_items),
        "processed": len(items),
        "stopped_early": stopped_early,
        "stop_reason": stop_reason,
        "genre_counts": genre_counts,
        "items": items,
        "unmatched_items": unmatched_items,
        "empty_genre_items": empty_genre_items,
    }


def save_tmdb_genre_distribution_report(report: dict[str, Any], output_dir: str | Path | None = None) -> Path:
    diagnostics_dir = ensure_diagnostics_dir(output_dir)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = diagnostics_dir / f"tmdb_genre_distribution_{timestamp}.json"
    with open(path, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return path


def candidate_to_csv_row(candidate: dict[str, Any]) -> dict[str, Any]:
    row = {}
    for field in CSV_FIELDS:
        value = candidate.get(field)
        if field == "production_countries":
            value = candidate.get("tmdb_production_countries")
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        row[field] = value
    return row


def build_summary_lines(result: dict[str, Any]) -> list[str]:
    """Возвращает строки итогового отчёта (печать выполняет UI/CLI)."""
    stats = result["stats"]
    lines = [
        f"Найдено через TMDb Discover: {stats['discover_total']}",
        f"Удалено дублей: {stats['duplicates_removed']}",
        f"Пропущено уже просмотренных: {stats['watched_skipped']}",
        f"Запрошено TMDb Details: {stats['details_requested']}",
        f"С IMDb ID: {stats['has_imdb_id']}",
        f"Найдено в IMDb dataset: {stats['found_in_imdb_sql']}",
        f"KP найдено в кэше: {stats['kp_cache_hit']}",
        f"KP API запросов: {stats['kp_api_requested']}",
        f"KP API найдено: {stats['kp_api_found']}",
        f"KP API не найдено: {stats['kp_api_not_found']}",
        f"KP API отклонено match-check: {stats['kp_api_rejected_by_match']}",
        f"KP API ошибок: {stats['kp_api_errors']}",
        f"KP API пропущено из-за кэша: {stats['kp_api_skipped_cache']}",
        f"KP ожидает добора из-за лимита: {stats['kp_pending_limit']}",
        f"Неполных кандидатов по KP: {stats['kp_incomplete_candidates']}",
        f"Полностью обогащённых кандидатов: {stats['complete_candidates']}",
        f"Прошли country_score: {stats['country_passed']}",
        f"Пограничный country_score: {stats['country_borderline']}",
        f"Отклонено по country_score: {stats['country_rejected']}",
        f"Отклонено adult/titleType: {stats['adult_title_type_rejected']}",
        f"Отклонено IMDb-фильтрами всего: {stats['imdb_filter_rejected']}",
        f"Итоговых кандидатов: {stats['final_candidates']}",
        "",
        "Топ-20 по final_score",
        "-" * 80,
    ]
    for index, candidate in enumerate(result["candidates"][:20], start=1):
        lines.append(
            f"{index:>2}. {candidate.get('final_score'):.3f} | "
            f"{candidate.get('title') or '-'} ({candidate.get('year') or '-'}) | "
            f"TMDb {candidate.get('tmdb_rating') or '-'} / {candidate.get('tmdb_votes') or 0} | "
            f"IMDb {candidate.get('imdb_rating') or '-'} / {candidate.get('imdb_votes') or 0}"
        )
    return lines

