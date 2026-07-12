"""Facade for SQLite candidate pool, criteria, and query repositories."""

from __future__ import annotations

from storage.sqlite.candidate_criteria_repository import (
    load_candidate_criteria_dict,
    save_candidate_criteria_dict,
)
from storage.sqlite.candidate_pool_repository import (
    clear_candidate_pool,
    load_candidate_pool_dict,
    merge_candidate_pool_dict,
    save_candidate_pool_dict,
)
from storage.sqlite.candidate_query_repository import (
    get_worst_candidate_records,
    query_candidate_records,
)


__all__ = [
    "clear_candidate_pool",
    "get_worst_candidate_records",
    "load_candidate_criteria_dict",
    "load_candidate_pool_dict",
    "merge_candidate_pool_dict",
    "query_candidate_records",
    "save_candidate_criteria_dict",
    "save_candidate_pool_dict",
]
