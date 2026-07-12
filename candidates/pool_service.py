"""Candidate-pool use cases exposed to UI and console callers."""

from __future__ import annotations

from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.pool.dataset_overlap import (
    count_pool_dataset_title_matches,
    purge_dataset_title_matches_from_pool,
)
from candidates.pool.dedupe import clean_common_pool_duplicates as _clean_common_pool_duplicates_impl
from candidates.pool.queries import get_all_candidates, is_candidate_incomplete
from candidates.pool.stats import build_pool_genre_count_rows, get_pool_stats
from candidates.pool.watched_cleanup import remove_candidate_from_pool
from candidates.repositories.criteria_repository import (
    build_criteria_label,
    clear_common_pool,
    ensure_common_pool_criteria as _ensure_common_pool_criteria_impl,
    load_candidate_criteria,
)
from candidates.views.formatters import format_pool_stats_lines, format_pool_stats_summary


def get_pool_view(criteria_name: str | None = None) -> list:
    """Return candidates for display without writing the SQLite candidate pool."""
    del criteria_name
    return get_all_candidates()


def get_pool_stats_view(criteria_name: str | None = None) -> dict:
    """Return pool stats and formatted lines for UI without writing JSON."""
    stats = get_pool_stats(criteria_name=criteria_name)
    return {
        "stats": stats,
        "lines": format_pool_stats_lines(stats),
        "summary": format_pool_stats_summary(stats),
    }


def get_pool_genre_count_rows() -> list[dict]:
    """Return read-only genre distribution rows for candidate-pool analytics."""
    return build_pool_genre_count_rows(get_pool_view())


def get_search_overview_view() -> dict:
    """Return the local candidate-search screen's pool overview."""
    stats_view = get_pool_stats_view()
    candidates = get_pool_view()
    return {
        "stats": stats_view["stats"],
        "lines": stats_view["lines"],
        "summary": stats_view["summary"],
        "candidates": candidates,
        "is_empty": stats_view["stats"]["storage_total"] == 0,
    }


def mark_candidate_watched_in_pool(candidate: dict) -> dict:
    """Remove a watched candidate through the existing title-and-year write path."""
    removed_count = remove_candidate_from_pool(candidate)
    message = (
        f"РР· pool СѓРґР°Р»РµРЅРѕ Р·Р°РїРёСЃРµР№: {removed_count}"
        if removed_count > 0
        else "РЎРѕРІРїР°РґР°СЋС‰РёС… Р·Р°РїРёСЃРµР№ РІ pool РЅРµ РЅР°Р№РґРµРЅРѕ"
    )
    return {
        "removed": removed_count > 0,
        "removed_count": removed_count,
        "message": message,
        "candidate": candidate,
    }


def get_mark_watched_view(criteria_name: str | None = None) -> dict:
    """Prepare candidates and pool stats for mark-watched UI."""
    del criteria_name
    candidates = get_pool_view()
    stats_view = get_pool_stats_view()
    return {
        "criteria_name": COMMON_POOL_CRITERIA_NAME,
        "candidates": candidates,
        "stats": stats_view["stats"],
        "lines": stats_view["lines"],
        "summary": stats_view["summary"],
        "is_empty": len(candidates) == 0,
    }


def is_pool_candidate_incomplete(candidate: dict) -> bool:
    """Return the incomplete flag for mark-watched UI."""
    return is_candidate_incomplete(candidate)


def clear_common_candidate_pool() -> dict:
    """Clear all candidates from the shared pool through the existing write path."""
    result = clear_common_pool()
    return {"cleared": result.get("cleared", 0), "criteria_name": COMMON_POOL_CRITERIA_NAME}


def clean_common_pool_duplicates(*, merge_similar: bool = True, merge_cross_year: bool = True) -> dict:
    """Remove exact, similar, and cross-year duplicates from the shared pool."""
    return _clean_common_pool_duplicates_impl(
        merge_similar=merge_similar,
        merge_cross_year=merge_cross_year,
    )


def get_pool_dataset_title_matches_view() -> dict:
    """Preview pool entries whose title is already present in the watched dataset."""
    return count_pool_dataset_title_matches()


def purge_pool_dataset_title_matches() -> dict:
    """Remove pool entries whose normalized title is already in the watched dataset."""
    return purge_dataset_title_matches_from_pool()


def delete_candidate_pool_criteria(criteria_name: str) -> dict:
    """Legacy alias that clears the single shared candidate pool."""
    del criteria_name
    result = clear_common_candidate_pool()
    return {
        "deleted": result["cleared"] > 0,
        "deleted_criteria": False,
        "deleted_candidates": result["cleared"],
        "criteria_name": COMMON_POOL_CRITERIA_NAME,
    }


def get_criteria_catalog_view() -> dict:
    """Return the single shared pool criteria entry for UI pickers."""
    all_criteria = load_candidate_criteria()
    criteria = all_criteria.get(COMMON_POOL_CRITERIA_NAME)
    items = []
    if isinstance(criteria, dict):
        items.append({
            "criteria_name": COMMON_POOL_CRITERIA_NAME,
            "criteria": criteria,
            "label": build_criteria_label(COMMON_POOL_CRITERIA_NAME, criteria),
        })
    return {
        "items": items,
        "by_name": {COMMON_POOL_CRITERIA_NAME: criteria} if isinstance(criteria, dict) else {},
        "is_empty": len(items) == 0,
    }


def get_common_pool_criteria_view() -> dict:
    """Return shared pool build/filter settings without writing JSON."""
    criteria = load_candidate_criteria().get(COMMON_POOL_CRITERIA_NAME)
    return {
        "criteria_name": COMMON_POOL_CRITERIA_NAME,
        "criteria": criteria if isinstance(criteria, dict) else {},
        "has_criteria": isinstance(criteria, dict),
    }


def ensure_common_pool_criteria() -> tuple[str, dict]:
    """Ensure the shared pool criteria entry exists."""
    return _ensure_common_pool_criteria_impl()
