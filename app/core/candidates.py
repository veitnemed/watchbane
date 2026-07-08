"""Search orchestration over saved candidate-pool records."""

from __future__ import annotations

from app.core.explain import explain_candidate
from app.core.filters import filter_candidates
from app.core.ranking import rank_candidates
from app.core import storage as search_storage


def search_candidates(candidates: list[dict], criteria: dict | None = None) -> dict:
    """Filters, ranks and explains saved candidates."""
    criteria = dict(criteria or {})
    criteria.setdefault("only_unwatched", True)
    criteria.setdefault("hide_hidden", True)
    criteria.setdefault("watched_identities", search_storage.load_watched_identities())
    criteria.setdefault("watched_title_keys", search_storage.load_watched_title_keys())
    criteria.setdefault("hidden_identities", search_storage.load_hidden_identities())

    filtered = filter_candidates(candidates, criteria)
    ranked = rank_candidates(filtered)
    for candidate in ranked:
        candidate["explanation"] = explain_candidate(candidate, criteria)
    return {
        "criteria": criteria,
        "filtered_candidates": filtered,
        "candidates": ranked,
        "filtered_count": len(filtered),
    }
