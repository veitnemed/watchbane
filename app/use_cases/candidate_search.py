"""Candidate search screen use cases."""

from __future__ import annotations

from candidates.pool_service import get_search_overview_view
from candidates.onboarding_service import replenish_candidate_pool_for_filters
from candidates.search_service import (
    DEFAULT_SEARCH_SORT_MODE,
    SEARCH_SORT_MODES,
    SEARCH_SORT_MODE_LABELS,
    get_search_filter_chip_options_view,
    get_search_filter_defaults_view,
    search_candidate_pool,
    search_candidate_pool_text,
    sort_search_candidates,
)


def load_candidate_search_screen(filters: dict, text_query: str | None = None) -> dict:
    """Load, filter, and sort the shared candidate pool for a search screen."""
    overview = get_search_overview_view()
    if overview.get("is_empty"):
        return {"overview": overview, "candidates": [], "filtered_candidates": [], "filtered_count": 0, "is_empty_pool": True}
    candidates = overview["candidates"]
    result = (
        search_candidate_pool_text(candidates, filters, text_query=text_query)
        if text_query else search_candidate_pool(candidates, filters)
    )
    return {"overview": overview, "is_empty_pool": False, **result}
