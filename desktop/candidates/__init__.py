"""Candidate search feature: session, filters, list, presenters."""

from desktop.candidates.filters_view import (
    APPLY_BUTTON_HEIGHT,
    APPLY_BUTTON_WIDTH_RATIO,
    CANDIDATE_YEAR_MIN,
    KP_SCORE_SLIDER_MAX,
    KP_SCORE_SLIDER_STEP,
    VOTES_SLIDER_MAX_INDEX,
    VOTES_SLIDER_STEPS,
    CandidateFiltersView,
)
from desktop.candidates.list_view import (
    CANDIDATE_DETAIL_STRETCH,
    CANDIDATE_LIST_MAX_WIDTH,
    CANDIDATE_LIST_MIN_WIDTH,
    CANDIDATE_LIST_STRETCH,
    CandidateListView,
)
from desktop.candidates.list_model import CandidateListModel, CandidateListRoles
from desktop.candidates.presenters import (
    SORT_MODE_METRIC_PREFIX,
    build_candidate_detail_entry,
    build_candidate_readonly_card,
    build_candidate_readonly_detail_entry,
    build_candidate_search_index,
    candidate_detail_identity,
    candidate_poster_url_for_download,
    candidate_search_text,
    filter_candidates_by_title,
    format_candidate_list_label,
    format_candidate_metric_value,
    format_candidate_title_line,
    resolve_local_poster_path_for_candidate,
)
from desktop.candidates.session import (
    DEFAULT_BROWSE_FILTERS,
    DEFAULT_SORT_MODE,
    CandidateSearchSession,
)
from desktop.candidates.workers.poster_worker import CandidatePosterDownloadWorker
from desktop.candidates.workers.search_worker import CandidateSearchWorker

__all__ = [
    "APPLY_BUTTON_HEIGHT",
    "APPLY_BUTTON_WIDTH_RATIO",
    "CANDIDATE_DETAIL_STRETCH",
    "CANDIDATE_LIST_MAX_WIDTH",
    "CANDIDATE_LIST_MIN_WIDTH",
    "CANDIDATE_LIST_STRETCH",
    "CANDIDATE_YEAR_MIN",
    "CandidateFiltersView",
    "CandidateListModel",
    "CandidateListRoles",
    "CandidateListView",
    "CandidatePosterDownloadWorker",
    "CandidateSearchWorker",
    "CandidateSearchSession",
    "DEFAULT_BROWSE_FILTERS",
    "DEFAULT_SORT_MODE",
    "KP_SCORE_SLIDER_MAX",
    "KP_SCORE_SLIDER_STEP",
    "SORT_MODE_METRIC_PREFIX",
    "VOTES_SLIDER_MAX_INDEX",
    "VOTES_SLIDER_STEPS",
    "build_candidate_detail_entry",
    "build_candidate_readonly_card",
    "build_candidate_readonly_detail_entry",
    "build_candidate_search_index",
    "candidate_detail_identity",
    "candidate_poster_url_for_download",
    "candidate_search_text",
    "filter_candidates_by_title",
    "format_candidate_list_label",
    "format_candidate_metric_value",
    "format_candidate_title_line",
    "resolve_local_poster_path_for_candidate",
]
