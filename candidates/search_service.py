"""Candidate search, filtering, ranking, and list actions."""

from __future__ import annotations

import os

from app.core import candidates as search_core
from candidates.scoring import ranking as search_ranking
from app.core import storage as search_storage
from candidates.models.keys import COMMON_POOL_CRITERIA_NAME, pool_entry_key
from candidates.pool.queries import is_candidate_incomplete
from candidates.pool.search_helpers import (
    build_search_filter_defaults,
    collect_search_country_options,
    collect_search_genre_options,
)
from candidates.pool_service import get_pool_view
from candidates.repositories.criteria_repository import load_candidate_criteria
from candidates.scoring.sort_keys import dedupe_ranked_candidates_by_title_identity
from candidates.sources.tmdb import country_options as tmdb_country_options
from candidates.views.formatters import (
    format_candidate_description as _format_candidate_description_impl,
    format_search_filter_default_lines,
)
from dataset import filter_popularity
from candidates.views import filter_popularity as pool_filter_popularity
from storage import data as storage_data


FTS_SEARCH_ENV = "WATCHBANE_FTS_SEARCH"
FTS_SEARCH_DEFAULT = True


def _persisted_fts_search_enabled() -> bool:
    try:
        from config import app_settings_store

        payload = app_settings_store.load_sqlite_settings_dict()
        if isinstance(payload, dict) is False:
            return FTS_SEARCH_DEFAULT
        value = payload.get("fts_search_enabled")
        if value in (None, ""):
            return FTS_SEARCH_DEFAULT
        if isinstance(value, str):
            return value.strip().casefold() not in ("0", "false", "no", "off")
        return bool(value)
    except Exception:
        return FTS_SEARCH_DEFAULT


def is_fts_search_enabled() -> bool:
    env_value = os.environ.get(FTS_SEARCH_ENV)
    if env_value == "1":
        return True
    if env_value == "0":
        return False
    return _persisted_fts_search_enabled()


def _candidate_pool_key(candidate: dict) -> str:
    stored = candidate.get("pool_entry_key")
    return str(stored) if stored not in (None, "") else pool_entry_key(candidate)


def get_search_filter_view(candidates: list, filters: dict) -> dict:
    """Apply runtime filters for local search without model scoring."""
    search_view = search_core.search_candidates(candidates, filters)
    filtered_candidates = search_view["candidates"]
    incomplete_candidates = [
        candidate for candidate in filtered_candidates if is_candidate_incomplete(candidate)
    ]
    return {
        "filtered_candidates": filtered_candidates,
        "ready_candidates": filtered_candidates,
        "incomplete_candidates": incomplete_candidates,
        "filtered_count": len(filtered_candidates),
        "ready_count": len(filtered_candidates),
        "skipped_incomplete_count": 0,
        "candidates": filtered_candidates,
    }


def get_search_filter_defaults_view(criteria_name: str | None = None) -> dict:
    """Return saved search-filter defaults for UI without writing JSON."""
    del criteria_name
    defaults = build_search_filter_defaults()
    lines = format_search_filter_default_lines(defaults)
    common_criteria = load_candidate_criteria().get(COMMON_POOL_CRITERIA_NAME)
    return {
        "defaults": defaults,
        "lines": lines,
        "has_defaults": isinstance(common_criteria, dict) and len(common_criteria) > 0,
    }


def get_search_genre_options_view(criteria_name: str | None = None) -> dict:
    """Return saved-pool genres available to search filters."""
    del criteria_name
    candidates = get_pool_view()
    genres = collect_search_genre_options(candidates)
    return {
        "criteria_name": COMMON_POOL_CRITERIA_NAME,
        "genres": genres,
        "count": len(genres),
        "label": "Р”РѕСЃС‚СѓРїРЅС‹Рµ Р¶Р°РЅСЂС‹ РґР»СЏ РїРѕРёСЃРєР° (РїРѕ СЃРѕС…СЂР°РЅС‘РЅРЅС‹Рј РґР°РЅРЅС‹Рј pool)",
    }


def get_search_filter_chip_options_view() -> dict:
    """Return watched-dataset genre/country options for popular-first filter chips."""
    dataset = storage_data.load_dataset()
    dataset_total = len(dataset) if isinstance(dataset, dict) else 0
    pool_candidates = get_pool_view()
    pool_genres = collect_search_genre_options(pool_candidates)
    pool_countries = collect_search_country_options(pool_candidates)
    genres = filter_popularity.build_dataset_genre_popularity(dataset)
    countries = filter_popularity.build_dataset_country_popularity(dataset)
    genres = pool_filter_popularity.merge_genre_popularity_with_pool(genres, pool_genres)
    countries = pool_filter_popularity.merge_country_popularity_with_pool(countries, pool_countries)
    source = "dataset" if dataset_total > 0 else "fallback"
    if not genres:
        source = "fallback"
        genres = [{"label": label, "count": 0} for label in pool_genres]
    if not countries:
        source = "fallback"
        countries = [
            {"code": option["code"], "label": option["label"], "count": 0}
            for option in tmdb_country_options.country_options()
        ]
    return {
        "genres": genres,
        "countries": countries,
        "dataset_total": dataset_total,
        "is_empty": dataset_total == 0,
        "source": source,
    }


def rank_search_candidates(candidates: list) -> dict:
    """Rank and dedupe candidates by explainable quality score."""
    scored_candidates = search_ranking.rank_candidates(candidates)
    before_dedupe_count = len(scored_candidates)
    scored_candidates = dedupe_ranked_candidates_by_title_identity(scored_candidates)
    return {
        "candidates": scored_candidates,
        "before_dedupe_count": before_dedupe_count,
        "hidden_duplicates": before_dedupe_count - len(scored_candidates),
    }


SEARCH_SORT_MODES = (
    "final_score", "quality_score", "tmdb_score", "tmdb_votes", "tmdb_popularity",
    "year", "text_relevance", "relevance",
)
SEARCH_SORT_MODE_LABELS = {
    "final_score": "РС‚РѕРі", "quality_score": "РљР°С‡РµСЃС‚РІРѕ", "tmdb_score": "TMDb",
    "tmdb_votes": "Р“РѕР»РѕСЃР° TMDb", "tmdb_popularity": "РџРѕРїСѓР»СЏСЂРЅРѕСЃС‚СЊ TMDb",
    "year": "Р“РѕРґ", "text_relevance": "РўРµРєСЃС‚", "relevance": "Р РµР»РµРІР°РЅС‚РЅРѕСЃС‚СЊ",
}
DEFAULT_SEARCH_SORT_MODE = "final_score"


def _sort_field_value(candidate: dict, field_name: str) -> float | None:
    from candidates.models.schema import coerce_candidate_number

    return coerce_candidate_number(candidate.get(field_name))


def _sort_candidates_by_mode(candidates: list, sort_mode: str) -> list:
    if sort_mode == "relevance":
        from candidates.search.rerank import sort_by_relevance

        return sort_by_relevance(list(candidates))
    field_name = sort_mode if sort_mode in SEARCH_SORT_MODES else DEFAULT_SEARCH_SORT_MODE
    if sort_mode == "text_relevance":
        def text_sort_key(candidate: dict) -> tuple:
            value = candidate.get("text_relevance_score")
            title = str(candidate.get("title") or candidate.get("name") or "").casefold()
            return (1, 0.0, title) if value is None else (0, float(value), title)
        return sorted(list(candidates), key=text_sort_key)

    def sort_key(candidate: dict) -> tuple:
        value = _sort_field_value(candidate, field_name)
        title = str(candidate.get("title") or candidate.get("name") or "").casefold()
        return (1, 0.0, title) if value is None else (0, -float(value), title)
    return sorted(list(candidates), key=sort_key)


def sort_search_candidates(candidates: list, sort_mode: str) -> dict:
    """Dedupe and sort filtered candidates by a numeric pool field."""
    normalized_mode = sort_mode if sort_mode in SEARCH_SORT_MODES else DEFAULT_SEARCH_SORT_MODE
    before_dedupe_count = len(candidates)
    deduped = dedupe_ranked_candidates_by_title_identity(list(candidates))
    sorted_candidates = _sort_candidates_by_mode(deduped, normalized_mode)
    return {
        "candidates": sorted_candidates,
        "sort_mode": normalized_mode,
        "before_dedupe_count": before_dedupe_count,
        "hidden_duplicates": before_dedupe_count - len(deduped),
    }


def search_candidate_pool(candidates: list, filters: dict) -> dict:
    """Filter and rank saved candidates for local search."""
    return search_core.search_candidates(candidates, filters)


def _prepare_text_search_criteria(filters: dict) -> dict:
    criteria = dict(filters or {})
    criteria.setdefault("only_unwatched", True)
    criteria.setdefault("hide_hidden", True)
    criteria.setdefault("watched_identities", search_storage.load_watched_identities())
    criteria.setdefault("watched_title_keys", search_storage.load_watched_title_keys())
    criteria.setdefault("hidden_identities", search_storage.load_hidden_identities())
    return criteria


def _search_candidate_pool_text_legacy(candidates: list, criteria: dict, *, normalized_query: str, fts_hits: list[tuple[str, float]]) -> dict:
    from candidates.search.match_fields import find_matched_fields
    from candidates.search.rerank import attach_text_relevance

    fts_keys = {pool_key for pool_key, _ in fts_hits}
    bm25_by_key = {pool_key: score for pool_key, score in fts_hits}
    search_view = search_candidate_pool(candidates, criteria)
    enriched_candidates = attach_text_relevance([
        candidate for candidate in search_view.get("candidates") or []
        if _candidate_pool_key(candidate) in fts_keys
    ], bm25_by_key)
    for candidate in enriched_candidates:
        candidate["matched_fields"] = find_matched_fields(candidate, normalized_query)
    return {
        **search_view, "candidates": enriched_candidates,
        "filtered_candidates": enriched_candidates, "filtered_count": len(enriched_candidates),
        "text_query": normalized_query, "text_relevance_by_key": bm25_by_key, "fts_enabled": True,
    }


def search_candidate_pool_text(candidates: list, filters: dict, *, text_query: str | None = None) -> dict:
    """Apply structural filters plus optional FTS retrieval."""
    normalized_query = str(text_query or "").strip()
    if normalized_query == "" or not is_fts_search_enabled():
        return search_candidate_pool(candidates, filters)
    import sqlite3
    from candidates.scoring.explain import explain_candidate
    from candidates.search.filtering import filter_candidates
    from candidates.scoring.ranking import rank_candidates
    from candidates.search.fts_index import search_fts, search_fts_prefiltered
    from candidates.search.match_fields import find_matched_fields
    from candidates.search.rerank import attach_text_relevance
    from candidates.search.structural_sql import build_structural_sql_filters
    from storage.sqlite.candidate_query_repository import load_candidate_records_by_pool_keys
    from storage.sqlite.connection import connect

    criteria = _prepare_text_search_criteria(filters)
    structural_clauses, structural_params = build_structural_sql_filters(criteria)
    conn = connect()
    try:
        fts_hits = search_fts_prefiltered(conn, normalized_query, structural_clauses=structural_clauses or None, structural_params=structural_params or None)
        if fts_hits:
            try:
                hit_candidates = load_candidate_records_by_pool_keys([key for key, _ in fts_hits], conn=conn)
                ranked = rank_candidates(filter_candidates(hit_candidates, criteria))
                for candidate in ranked:
                    candidate["explanation"] = explain_candidate(candidate, criteria)
                bm25_by_key = {pool_key: score for pool_key, score in fts_hits}
                enriched_candidates = attach_text_relevance(ranked, bm25_by_key)
                for candidate in enriched_candidates:
                    candidate["matched_fields"] = find_matched_fields(candidate, normalized_query)
                return {"criteria": criteria, "filtered_candidates": enriched_candidates, "candidates": enriched_candidates, "filtered_count": len(enriched_candidates), "text_query": normalized_query, "text_relevance_by_key": bm25_by_key, "fts_enabled": True}
            except sqlite3.OperationalError:
                return _search_candidate_pool_text_legacy(candidates, criteria, normalized_query=normalized_query, fts_hits=fts_hits)
        fts_hits = search_fts(conn, normalized_query)
    finally:
        conn.close()
    return _search_candidate_pool_text_legacy(candidates, criteria, normalized_query=normalized_query, fts_hits=fts_hits)


def add_candidate_to_watchlist(candidate: dict) -> dict:
    """Add a candidate to the local watchlist JSON."""
    return search_storage.add_to_watchlist(candidate)


def hide_candidate(candidate: dict) -> dict:
    """Add a candidate to the local hidden JSON."""
    return search_storage.add_to_hidden(candidate)


def format_candidate_description(candidate: dict, limit: int = 200) -> str:
    """Return a truncated candidate description for UI cards."""
    return _format_candidate_description_impl(candidate, limit=limit)
