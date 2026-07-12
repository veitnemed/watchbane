"""Candidate-pool mutation use cases."""

from __future__ import annotations

from candidates.pool_service import mark_candidate_watched_in_pool
from candidates.search_service import add_candidate_to_watchlist, hide_candidate

__all__ = ["add_candidate_to_watchlist", "hide_candidate", "mark_candidate_watched_in_pool"]
