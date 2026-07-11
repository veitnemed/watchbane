"""User-facing recommendation preference contracts."""

from candidates.preferences.discovery import CandidateDiscoveryPreferences
from candidates.preferences.simple import SimpleRecommendationPreferences
from candidates.preferences.vector import (
    RecommendationVector,
    resolve_diversity_window,
    resolve_exploration_ratio,
    resolve_rarity_weights,
)

__all__ = [
    "CandidateDiscoveryPreferences",
    "RecommendationVector",
    "SimpleRecommendationPreferences",
    "resolve_diversity_window",
    "resolve_exploration_ratio",
    "resolve_rarity_weights",
]
