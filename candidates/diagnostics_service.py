"""Candidate-pool diagnostics use cases."""

from __future__ import annotations

from candidates.pool.diagnostics import (
    build_candidate_poster_diagnostics,
    build_title_duplicate_summary,
    find_cross_year_title_groups,
    find_suspicious_duplicates,
    find_title_duplicate_groups,
)
from candidates.pool.queries import get_incomplete_candidates
from candidates.pool_service import get_pool_stats_view, get_search_overview_view
from candidates.repositories.pool_repository import load_candidate_pool


def get_metadata_diagnostics_view(criteria_name: str | None = None) -> dict:
    """Prepare incomplete TMDb/core metadata diagnostics without writing JSON."""
    del criteria_name
    pool = load_candidate_pool()
    incomplete_candidates = get_incomplete_candidates(pool, criteria_name=None)
    return {"is_empty": len(pool) == 0, "incomplete_candidates": incomplete_candidates, "incomplete_count": len(incomplete_candidates)}


def get_suspicious_duplicates_view() -> dict:
    """Prepare suspicious duplicate pairs for diagnostics UI."""
    pairs = find_suspicious_duplicates()
    return {"pairs": pairs, "count": len(pairs), "is_empty": len(pairs) == 0}


def get_cross_year_duplicates_view() -> dict:
    """Prepare cross-year duplicate groups for diagnostics UI."""
    groups = find_cross_year_title_groups()
    return {"groups": groups, "count": len(groups), "is_empty": len(groups) == 0}


def get_title_duplicates_view() -> dict:
    """Prepare title duplicate groups and summary for diagnostics UI."""
    groups = find_title_duplicate_groups()
    summary = build_title_duplicate_summary(groups)
    return {
        "groups": groups, "summary": summary, "group_count": summary["group_count"],
        "extra_entries": summary["extra_entries"], "reported_groups": summary["reported_groups"],
        "dataset_overlap_count": summary["dataset_overlap_count"], "count": summary["reported_groups"],
        "is_empty": len(groups) == 0,
    }


def get_candidate_poster_diagnostics_view() -> dict:
    """Prepare poster coverage diagnostics for saved-pool candidates."""
    overview = get_search_overview_view()
    if overview.get("is_empty"):
        return {"is_empty_pool": True, "is_empty": True, "total": 0, "counts": {"displayable": 0, "metadata_only": 0, "missing": 0}, "source_counts": {}, "problem_rows": []}
    return {"is_empty_pool": False, **build_candidate_poster_diagnostics(overview["candidates"])}


def get_console_candidate_summary_view() -> dict:
    """Return compact candidate-pool counters for the main console menu."""
    stats_view = get_pool_stats_view()
    poster_view = get_candidate_poster_diagnostics_view()
    stats, counts = stats_view.get("stats") or {}, poster_view.get("counts") or {}
    total = int(stats.get("unique_total") or stats.get("storage_total") or 0)
    complete = int(stats.get("ready_total") or 0)
    incomplete = int(stats.get("incomplete_total") or max(0, total - complete))
    posters_displayable = int(counts.get("displayable") or 0)
    posters_to_download = int(counts.get("metadata_only") or 0)
    posters_missing_metadata = int(counts.get("missing") or 0)
    return {
        "total": total, "complete": complete, "incomplete": incomplete,
        "posters_displayable": posters_displayable, "posters_to_download": posters_to_download,
        "posters_missing_metadata": posters_missing_metadata,
        "line": f"Candidate pool: {total} | complete: {complete} | posters: {posters_displayable} | need posters: {posters_to_download}",
    }
