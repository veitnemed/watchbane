"""Public facade for watched dataset operations."""

from dataset.add_title_service import (
    AddTitleResolveBundle,
    build_candidate_transfer_bundle,
    resolve_title_for_add,
    save_add_title_record,
)
from dataset.dataset_records import add_dataset_record, update_dataset_record
from dataset.delete_record import delete_watched_record
from dataset.score_analytics import build_score_analytics
from dataset.stats.summary import build_dataset_info_lines, get_dataset_stats

__all__ = [
    "AddTitleResolveBundle",
    "add_dataset_record",
    "build_candidate_transfer_bundle",
    "build_dataset_info_lines",
    "build_score_analytics",
    "delete_watched_record",
    "get_dataset_stats",
    "resolve_title_for_add",
    "save_add_title_record",
    "update_dataset_record",
]
