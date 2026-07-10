"""Public facade for watched dataset operations."""

from dataset.add_flow.bundle import (
    AddTitleResolveBundle,
    build_add_title_resolve_bundle,
    resolve_title_for_add,
)
from dataset.add_flow.preview import (
    build_preview_card_from_defaults,
    build_preview_movie_from_defaults,
)
from dataset.add_flow.save import build_movie_record_from_defaults, save_add_title_record
from dataset.add_flow.status import format_resolve_status_lines
from dataset.add_flow.transfer import build_candidate_transfer_bundle
from dataset.analytics.build import build_score_analytics
from dataset.analytics.completeness import summarize_dataset_completeness
from dataset.analytics.reports import (
    TMDB_DELTA_LIST_PREVIEW_LIMIT,
    format_rating_gap_line,
    format_suspicious_rating_line,
    format_tmdb_delta_line,
)
from dataset.genres.stats import (
    build_dataset_genre_catalog,
    show_dataset_genre_catalog,
    show_dataset_genres,
)
from dataset.models.results import AddRecordResult, UpdateRecordResult
from dataset.read_models.watched import (
    WatchedEntry,
    build_watched_lookup_cache,
    load_watched_entries,
    prepare_card_for_display,
    reload_poster_cache,
)
from dataset.records.add import add_dataset_record
from dataset.records.delete import (
    backup_before_watched_delete,
    build_watched_delete_preview,
    delete_watched_record as _delete_watched_record_impl,
    search_watched_records_by_query,
)
from dataset.records.update import update_dataset_record
from dataset.stats.summary import build_dataset_info_lines, get_dataset_stats
from dataset.storage_movie import add_movie
from dataset.title_resolve import (
    ADD_TITLE_RESOLVE_PROGRESS_TOTAL,
    build_add_meta_payload,
    build_api_defaults,
    build_candidate_genre_transfer_preview,
    build_candidate_meta_payload,
    build_candidate_transfer_payload,
    build_empty_add_defaults,
    build_tmdb_add_defaults,
    build_poster_hints_from_candidate,
    build_poster_hints_from_resolve,
    resolve_title_data_for_add,
)
from dataset.views.delete_formatters import (
    format_watched_delete_preview,
    format_watched_delete_report,
)


def delete_watched_record(dataset_key: str, *, timestamp: str | None = None) -> dict:
    """Delete one watched record; returns legacy dict for existing callers."""
    return _delete_watched_record_impl(dataset_key, timestamp=timestamp).to_dict()


__all__ = [
    "ADD_TITLE_RESOLVE_PROGRESS_TOTAL",
    "AddRecordResult",
    "AddTitleResolveBundle",
    "TMDB_DELTA_LIST_PREVIEW_LIMIT",
    "UpdateRecordResult",
    "WatchedEntry",
    "add_dataset_record",
    "add_movie",
    "backup_before_watched_delete",
    "build_add_meta_payload",
    "build_add_title_resolve_bundle",
    "build_api_defaults",
    "build_candidate_genre_transfer_preview",
    "build_candidate_meta_payload",
    "build_candidate_transfer_bundle",
    "build_candidate_transfer_payload",
    "build_dataset_genre_catalog",
    "build_dataset_info_lines",
    "build_empty_add_defaults",
    "build_tmdb_add_defaults",
    "build_movie_record_from_defaults",
    "build_poster_hints_from_candidate",
    "build_poster_hints_from_resolve",
    "build_preview_card_from_defaults",
    "build_preview_movie_from_defaults",
    "build_score_analytics",
    "build_watched_delete_preview",
    "build_watched_lookup_cache",
    "delete_watched_record",
    "format_rating_gap_line",
    "format_resolve_status_lines",
    "format_suspicious_rating_line",
    "format_tmdb_delta_line",
    "format_watched_delete_preview",
    "format_watched_delete_report",
    "get_dataset_stats",
    "load_watched_entries",
    "prepare_card_for_display",
    "reload_poster_cache",
    "resolve_title_data_for_add",
    "resolve_title_for_add",
    "save_add_title_record",
    "search_watched_records_by_query",
    "show_dataset_genre_catalog",
    "show_dataset_genres",
    "summarize_dataset_completeness",
    "update_dataset_record",
]
