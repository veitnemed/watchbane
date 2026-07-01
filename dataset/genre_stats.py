"""Compatibility wrapper for dataset genre statistics and catalog."""

from dataset.genres.stats import (
    build_dataset_genre_catalog,
    count_genres_from_api,
    extract_genres,
    get_dataset_title,
    print_genre_report,
    show_dataset_genre_catalog,
    show_dataset_genres,
)

__all__ = [
    "build_dataset_genre_catalog",
    "count_genres_from_api",
    "extract_genres",
    "get_dataset_title",
    "print_genre_report",
    "show_dataset_genre_catalog",
    "show_dataset_genres",
]
