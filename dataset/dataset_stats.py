"""Compatibility wrapper for dataset summary statistics."""

from dataset.stats.summary import (
    build_dataset_info_lines,
    collect_dataset_values,
    get_dataset_stats,
    get_feature_label,
)

__all__ = [
    "build_dataset_info_lines",
    "collect_dataset_values",
    "get_dataset_stats",
    "get_feature_label",
]
