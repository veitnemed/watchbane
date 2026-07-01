"""Source priority merge for add-flow defaults."""

from config import scheme
from dataset.resolve.countries import extract_country_value
from dataset.resolve.defaults import (
    build_empty_add_defaults,
    extract_api_description,
    extract_api_raw_scores,
    extract_api_title,
)
from dataset.resolve.genres import build_genre_defaults, extract_api_genres, extract_tmdb_genres
from dataset.resolve.helpers import unique_preserve_order
from dataset.resolve.identity import is_sql_candidate_identity_safe


def first_value(*items):
    """Возвращает первое непустое значение и его источник."""
    for value, source in items:
        if value is not None and value != "" and value != []:
            return value, source
    return None, None


def extract_tmdb_title(series: dict | None) -> str:
    """Возвращает название из нормализованного TMDb-объекта."""
    if not isinstance(series, dict):
        return ""
    for key in ("title", "original_title"):
        value = str(series.get(key) or "").strip()
        if value:
            return value
    return ""


def build_add_defaults_by_priority(
    input_title: str,
    sql_data: dict | None,
    api_data: dict | None,
    tmdb_data: dict | None,
    sql_source: str = "imdb_sql",
) -> dict:
    """Собирает defaults для добавления записи по зафиксированным приоритетам источников."""
    defaults = build_empty_add_defaults(input_title)
    sources = {
        "title": None,
        "year": None,
        "country": None,
        "imdb_score": None,
        "imdb_votes": None,
        "kp_score": None,
        "kp_votes": None,
        "genres": None,
        "description": None,
    }
    source_values = {
        "genres": [],
        "description": None,
    }

    api_identity_candidate = api_data if api_data is not None else tmdb_data
    sql_identity_accepted, sql_identity_reason = is_sql_candidate_identity_safe(
        sql_data,
        api_identity_candidate,
        input_title,
    )
    effective_sql_data = sql_data if sql_identity_accepted else None
    api_scores = extract_api_raw_scores(api_data) if api_data is not None else {}
    api_genres = extract_api_genres(api_data) if api_data is not None else []
    sql_genres = unique_preserve_order((effective_sql_data or {}).get("genres", []) or [])
    tmdb_genres = extract_tmdb_genres(tmdb_data)

    title_value, title_source = first_value(
        (extract_api_title(api_data) if api_data is not None else None, "kp_api"),
        (input_title, "input"),
        (extract_tmdb_title(tmdb_data), "tmdb_api"),
        ((effective_sql_data or {}).get("title") or (effective_sql_data or {}).get("original_title"), sql_source),
    )
    year_value, year_source = first_value(
        ((api_data or {}).get("year"), "kp_api"),
        ((effective_sql_data or {}).get("year"), sql_source),
        ((tmdb_data or {}).get("year"), "tmdb_api"),
    )
    country_value, country_source = first_value(
        (extract_country_value(api_data), "kp_api"),
        (extract_country_value(tmdb_data), "tmdb_api"),
        (extract_country_value(effective_sql_data), sql_source),
    )
    imdb_score, imdb_score_source = first_value(
        ((effective_sql_data or {}).get("imdb_rating"), sql_source),
        (api_scores.get("imdb_score"), "kp_api"),
    )
    imdb_votes, imdb_votes_source = first_value(
        ((effective_sql_data or {}).get("imdb_votes"), sql_source),
        (api_scores.get("imdb_votes"), "kp_api"),
    )
    kp_score, kp_score_source = first_value((api_scores.get("kp_score"), "kp_api"))
    kp_votes, kp_votes_source = first_value((api_scores.get("kp_votes"), "kp_api"))
    genres, genres_source = first_value(
        (api_genres, "kp_api"),
        (tmdb_genres, "tmdb_api"),
        (sql_genres, sql_source),
    )
    description, description_source = first_value(
        (extract_api_description(api_data) if api_data is not None else None, "kp_api"),
        ((tmdb_data or {}).get("overview"), "tmdb_api"),
    )

    defaults[scheme.MAIN_INFO]["title"] = title_value or input_title
    defaults[scheme.MAIN_INFO]["year"] = year_value
    defaults[scheme.MAIN_INFO]["country"] = country_value
    defaults[scheme.RAW_SCORES]["imdb_score"] = imdb_score
    defaults[scheme.RAW_SCORES]["imdb_votes"] = imdb_votes
    defaults[scheme.RAW_SCORES]["kp_score"] = kp_score
    defaults[scheme.RAW_SCORES]["kp_votes"] = kp_votes
    defaults[scheme.GENRE] = build_genre_defaults(genres or [])

    sources["title"] = title_source
    sources["year"] = year_source
    sources["country"] = country_source
    sources["imdb_score"] = imdb_score_source
    sources["imdb_votes"] = imdb_votes_source
    sources["kp_score"] = kp_score_source
    sources["kp_votes"] = kp_votes_source
    sources["genres"] = genres_source
    sources["description"] = description_source
    source_values["genres"] = genres or []
    source_values["description"] = description

    return {
        "defaults": defaults,
        "sources": sources,
        "source_values": source_values,
        "sql_identity": {
            "accepted": sql_identity_accepted,
            "reason": sql_identity_reason,
        },
    }
