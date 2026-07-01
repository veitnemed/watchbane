"""Compatibility wrapper for watched record deletion."""

from storage import data as storage_data
from posters.cache import load_poster_cache, save_poster_cache
from dataset.records.delete import (
    backup_before_watched_delete,
    build_watched_delete_preview,
    delete_watched_record as _delete_watched_record,
    search_watched_records_by_query,
)
from dataset.views.delete_formatters import (
    format_watched_delete_preview,
    format_watched_delete_report,
)

__all__ = [
    "backup_before_watched_delete",
    "build_watched_delete_preview",
    "delete_watched_record",
    "format_watched_delete_preview",
    "format_watched_delete_report",
    "load_poster_cache",
    "save_poster_cache",
    "search_watched_records_by_query",
    "storage_data",
]


def delete_watched_record(dataset_key: str, *, timestamp: str | None = None) -> dict:
    """Delete one watched record; returns legacy dict for existing callers."""
    return _delete_watched_record(dataset_key, timestamp=timestamp).to_dict()
