"""Public candidate service facade for UI and console compatibility."""

from candidates.diagnostics_service import (
    get_candidate_poster_diagnostics_view,
    get_console_candidate_summary_view,
    get_cross_year_duplicates_view,
    get_metadata_diagnostics_view,
    get_suspicious_duplicates_view,
    get_title_duplicates_view,
)
from candidates.onboarding_service import (
    POOL_REPLENISH_THRESHOLD,
    STARTER_POOL_TARGET,
    build_onboarding_candidate_pool,
    get_onboarding_autofill_plan_view,
    get_pool_replenish_view,
    load_last_onboarding_profile,
    replenish_candidate_pool,
    replenish_candidate_pool_for_filters,
    should_show_onboarding_autofill,
)
from candidates.pool_service import (
    clean_common_pool_duplicates,
    clear_common_candidate_pool,
    delete_candidate_pool_criteria,
    ensure_common_pool_criteria,
    get_common_pool_criteria_view,
    get_criteria_catalog_view,
    get_mark_watched_view,
    get_pool_dataset_title_matches_view,
    get_pool_genre_count_rows,
    get_pool_stats_view,
    get_pool_view,
    get_search_overview_view,
    is_pool_candidate_incomplete,
    mark_candidate_watched_in_pool,
    purge_pool_dataset_title_matches,
)
from candidates.poster_service import download_candidate_pool_preview_posters
from candidates.search_service import (
    DEFAULT_SEARCH_SORT_MODE,
    FTS_SEARCH_DEFAULT,
    FTS_SEARCH_ENV,
    SEARCH_SORT_MODES,
    SEARCH_SORT_MODE_LABELS,
    add_candidate_to_watchlist,
    format_candidate_description,
    get_search_filter_chip_options_view,
    get_search_filter_defaults_view,
    get_search_filter_view,
    get_search_genre_options_view,
    hide_candidate,
    is_fts_search_enabled,
    rank_search_candidates,
    search_candidate_pool,
    search_candidate_pool_text,
    sort_search_candidates,
)
from candidates.tmdb_acquisition_service import (
    build_and_save_tmdb_candidate_pool,
    build_tmdb_candidate_pool,
    build_tmdb_criteria_name,
    get_tmdb_import_files_view,
    import_tmdb_result_to_pool,
    load_tmdb_result_import_preview,
    save_tmdb_build_result,
)


__all__ = [name for name in globals() if not name.startswith("_")]
