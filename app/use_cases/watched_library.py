"""Watched-library operations for desktop entry points."""

from __future__ import annotations

from dataset import service as dataset_service
from dataset.models.user_rating import normalize_user_rating


def load_watched_library(*, data_language: str = "ru") -> list:
    """Load watched entries already prepared for display."""
    return dataset_service.load_watched_entries(data_language=data_language)


def get_watched_delete_preview(dataset_key: str) -> dict | None:
    """Load a read-only preview for a destructive watched-record action."""
    return dataset_service.build_watched_delete_preview(dataset_key)


def delete_watched_title(dataset_key: str) -> dict:
    """Delete a watched title through the dataset service boundary."""
    return dataset_service.delete_watched_record(dataset_key)


def update_user_score(dataset_key: str, score: int):
    """Persist a validated personal score for one watched title."""
    normalized = normalize_user_rating(score)
    if normalized is None:
        raise ValueError("user_score must be an integer from 1 to 3")
    return dataset_service.update_dataset_record(
        dataset_key,
        {"main_info": {"user_score": normalized}},
        source_name="desktop_gui",
    )
