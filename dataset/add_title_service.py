"""Compatibility wrapper for add-title resolve, preview, and save."""

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
from dataset.storage_movie import add_movie

__all__ = [
    "AddTitleResolveBundle",
    "add_movie",
    "build_add_title_resolve_bundle",
    "build_candidate_transfer_bundle",
    "build_movie_record_from_defaults",
    "build_preview_card_from_defaults",
    "build_preview_movie_from_defaults",
    "format_resolve_status_lines",
    "resolve_title_for_add",
    "save_add_title_record",
]
