"""Thin public facade for TMDb-only add-title and candidate transfer helpers."""

from __future__ import annotations

from dataset.meta.payload import build_add_meta_payload, build_candidate_meta_payload
from dataset.resolve.defaults import build_api_defaults, build_empty_add_defaults, build_tmdb_add_defaults
from dataset.resolve.poster_hints import (
    build_poster_hints_from_candidate,
    build_poster_hints_from_resolve,
)
from dataset.resolve.service import (
    ADD_TITLE_RESOLVE_PROGRESS_TOTAL,
    print_progress_step,
    resolve_title_data,
    resolve_title_data_for_add,
)
from dataset.transfer.candidate import (
    build_candidate_genre_transfer_preview,
    build_candidate_transfer_genre_defaults,
    build_candidate_transfer_payload,
)

__all__ = [
    "ADD_TITLE_RESOLVE_PROGRESS_TOTAL",
    "build_add_meta_payload",
    "build_api_defaults",
    "build_candidate_genre_transfer_preview",
    "build_candidate_meta_payload",
    "build_candidate_transfer_genre_defaults",
    "build_candidate_transfer_payload",
    "build_empty_add_defaults",
    "build_poster_hints_from_candidate",
    "build_poster_hints_from_resolve",
    "build_tmdb_add_defaults",
    "print_progress_step",
    "resolve_title_data",
    "resolve_title_data_for_add",
]
