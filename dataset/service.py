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
    IMDB_DELTA_LIST_PREVIEW_LIMIT,
    format_imdb_delta_line,
    format_rating_gap_line,
    format_suspicious_rating_line,
)
from dataset.excel.export import export_dataset_to_excel
from dataset.excel.import_flow import replace_dataset_from_excel
from dataset.genres.import_flow import apply_genre_markup
from dataset.genres.stats import (
    build_dataset_genre_catalog,
    show_dataset_genre_catalog,
    show_dataset_genres,
)
from dataset.models.results import AddRecordResult, UpdateRecordResult
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
from dataset.tags_work import (
    add_tag,
    backup_tag_files,
    delete_all_tags,
    delete_tag,
    is_correct_tag_name,
    load_tags,
    move_edit_files_to_backup,
    save_tags,
)
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
    "IMDB_DELTA_LIST_PREVIEW_LIMIT",
    "UpdateRecordResult",
    "add_dataset_record",
    "add_movie",
    "add_tag",
    "apply_genre_markup",
    "backup_before_watched_delete",
    "backup_tag_files",
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
    "delete_all_tags",
    "delete_tag",
    "delete_watched_record",
    "export_dataset_to_excel",
    "format_imdb_delta_line",
    "format_rating_gap_line",
    "format_resolve_status_lines",
    "format_suspicious_rating_line",
    "format_watched_delete_preview",
    "format_watched_delete_report",
    "get_dataset_stats",
    "is_correct_tag_name",
    "load_tags",
    "move_edit_files_to_backup",
    "replace_dataset_from_excel",
    "resolve_title_data_for_add",
    "resolve_title_for_add",
    "save_add_title_record",
    "save_tags",
    "search_watched_records_by_query",
    "show_dataset_genre_catalog",
    "show_dataset_genres",
    "summarize_dataset_completeness",
    "update_dataset_record",
]
