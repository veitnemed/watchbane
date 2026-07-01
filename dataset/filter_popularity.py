"""Compatibility wrapper for watched dataset popularity aggregates."""

from dataset.stats.popularity import (
    build_dataset_country_popularity,
    build_dataset_genre_popularity,
)

__all__ = [
    "build_dataset_country_popularity",
    "build_dataset_genre_popularity",
]
