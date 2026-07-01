"""Compatibility wrapper: title resolve split across dataset.resolve and dataset.transfer."""

from apis import imdb_sql as sql_search
from apis import kp_api as api
from dataset.meta.payload import build_add_meta_payload, build_candidate_meta_payload
from dataset.resolve.defaults import (
    build_api_defaults,
    build_empty_add_defaults,
    build_sql_defaults,
    extract_api_description,
    extract_api_raw_scores,
    extract_api_title,
    has_api_imdb_values,
    merge_defaults,
)
from dataset.resolve.genres import (
    build_genre_defaults,
    extract_api_genres,
    extract_candidate_fallback_genres,
    extract_tmdb_genres,
    split_known_genres,
)
from dataset.resolve.helpers import (
    extract_candidate_imdb_id,
    extract_candidate_year,
    unique_preserve_order,
)
from dataset.resolve.identity import (
    extract_api_identity_titles,
    extract_api_original_title,
    extract_sql_identity_titles,
    is_sql_candidate_identity_safe,
    iter_sql_result_candidates,
    normalize_identity_title,
    resolve_sql_after_api_mismatch,
    sql_titles_match_identity,
    title_identity_match,
)
from dataset.resolve.poster_hints import (
    build_poster_hints_from_candidate,
    build_poster_hints_from_resolve,
)
from dataset.resolve.priority import build_add_defaults_by_priority, extract_tmdb_title, first_value
from dataset.resolve.service import (
    ADD_TITLE_RESOLVE_PROGRESS_TOTAL,
    print_progress_step,
    resolve_title_data,
    resolve_title_data_for_add,
)
from dataset.resolve.sources import (
    extract_api_countries,
    fetch_series_raw,
    format_series_lines,
    search_tmdb_defaults_data,
)
from dataset.resolve.status import get_kp_status, get_sql_status
from dataset.transfer.candidate import (
    build_candidate_genre_transfer_preview,
    build_candidate_transfer_genre_defaults,
    build_candidate_transfer_payload,
)

try:
    from apis import tmdb_api as api_tmdb
except ImportError:  # pragma: no cover
    api_tmdb = None

__all__ = [
    "ADD_TITLE_RESOLVE_PROGRESS_TOTAL",
    "api",
    "api_tmdb",
    "build_add_defaults_by_priority",
    "build_add_meta_payload",
    "build_api_defaults",
    "build_candidate_genre_transfer_preview",
    "build_candidate_meta_payload",
    "build_candidate_transfer_genre_defaults",
    "build_candidate_transfer_payload",
    "build_empty_add_defaults",
    "build_genre_defaults",
    "build_poster_hints_from_candidate",
    "build_poster_hints_from_resolve",
    "build_sql_defaults",
    "extract_api_countries",
    "extract_api_description",
    "extract_api_genres",
    "extract_api_identity_titles",
    "extract_api_original_title",
    "extract_api_raw_scores",
    "extract_api_title",
    "extract_candidate_fallback_genres",
    "extract_candidate_imdb_id",
    "extract_candidate_year",
    "extract_sql_identity_titles",
    "extract_tmdb_genres",
    "extract_tmdb_title",
    "fetch_series_raw",
    "first_value",
    "format_series_lines",
    "get_kp_status",
    "get_sql_status",
    "has_api_imdb_values",
    "is_sql_candidate_identity_safe",
    "iter_sql_result_candidates",
    "merge_defaults",
    "normalize_identity_title",
    "print_progress_step",
    "resolve_sql_after_api_mismatch",
    "resolve_title_data",
    "resolve_title_data_for_add",
    "search_tmdb_defaults_data",
    "split_known_genres",
    "sql_search",
    "sql_titles_match_identity",
    "title_identity_match",
    "unique_preserve_order",
]
