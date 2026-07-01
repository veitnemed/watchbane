"""Compatibility wrapper for saved candidate pool operations."""

from __future__ import annotations

from candidates.pool.completeness import (  # noqa: F401
    append_signal,
    get_available_genres,
    is_candidate_complete,
    normalize_genre_list,
)
from candidates.repositories.criteria_repository import (
    build_criteria_label,
    clear_common_pool,
    delete_criteria_and_candidates,
    ensure_common_pool_criteria,
    init_candidate_criteria,
    load_candidate_criteria,
    patch_criteria_filters,
    save_candidate_criteria,
    save_named_criteria,
)
from candidates.repositories.pool_repository import (
    init_candidate_pool,
    load_candidate_pool,
    save_candidate_pool,
)
from candidates.pool.dedupe import (
    candidate_key,
    candidate_pool_key,
    candidates_are_same,
    clean_common_pool_duplicates,
    deduplicate_pool,
    dedupe_pool_by_similar_titles,
    dedupe_pool_cross_year_titles,
)
from candidates.pool.normalization import (
    migrate_pool_keys,
    normalize_or_migrate_candidate_pool_file,
    normalize_pool,
    normalize_storage_pool,
)
from candidates.scoring.sort_keys import (
    candidate_sort_score,
    dedupe_ranked_candidates_by_title_identity,
)
from candidates.pool.dataset_overlap import (
    build_dataset_entries_by_title_key,
    build_dataset_title_keys,
    count_pool_dataset_title_matches,
    is_dataset_title_match,
    purge_dataset_title_matches_from_pool,
)
from candidates.pool.queries import (
    get_all_candidates,
    get_candidates_by_criteria,
    get_incomplete_candidates,
    is_candidate_incomplete,
)
from candidates.pool.stats import (
    POOL_GENRE_COUNT_CHART_LIMIT,
    POOL_GENRE_COUNT_TITLE_LIMIT,
    build_pool_genre_count_rows,
    get_pool_stats,
)
from candidates.pool.watched_cleanup import (
    build_watched_signatures,
    is_watched_candidate,
    purge_watched_from_pool,
    remove_candidate_from_pool,
    remove_watched_candidates,
)
from candidates.pool.diagnostics import (
    build_candidate_poster_diagnostics,
    build_title_duplicate_summary,
    classify_candidate_poster_state,
    collect_unique_pool_poster_urls,
    find_cross_year_title_groups,
    find_suspicious_duplicates,
    find_title_duplicate_groups,
)
from candidates.pool.search_helpers import (
    build_search_filter_defaults,
    collect_search_country_options,
    collect_search_genre_options,
    filter_saved_candidates_for_search,
)
from candidates.views.formatters import (
    format_candidate_description,
    format_pool_stats_lines,
    format_pool_stats_summary,
    format_search_filter_default_lines,
)
from candidates.pool.legacy_collect import collect_candidates
from candidates.sources.kp.retry import retry_kp_enrichment_for_pool
