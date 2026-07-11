"""Watched user_score write helpers (no Qt)."""

from __future__ import annotations

from desktop.i18n import tr
from dataset.models.user_rating import normalize_user_rating
from desktop.watched.model.load import WatchedEntry


def normalize_user_score_value(score) -> int | None:
    return normalize_user_rating(score)


def get_user_score_spin_value(card: dict) -> int | None:
    return normalize_user_rating(card.get("user_score"))


def build_user_score_update_payload(user_score: int) -> dict:
    """Build update_dataset_record patch for user_score only."""
    normalized = normalize_user_rating(user_score)
    if normalized is None:
        raise ValueError("user_score must be an integer from 1 to 3")
    return {"main_info": {"user_score": normalized}}


def save_watched_user_score(dataset_key: str, user_score: int):
    """Save user_score for a watched record via the dataset update pipeline."""
    from dataset import service

    return service.update_dataset_record(
        dataset_key,
        build_user_score_update_payload(user_score),
        source_name="desktop_gui",
    )


def format_save_user_score_status(result) -> str:
    """Short GUI status text after save attempt."""
    if result.ok and result.reason == "updated":
        return tr("watched.score.status.saved")
    if result.ok and result.reason == "nothing_changed":
        return tr("watched.score.status.no_changes")
    return result.message


def validate_score_edit_entry(entry: WatchedEntry | None) -> tuple[bool, str]:
    """Validate that a watched entry can be used for score edit dialog."""
    if entry is None:
        return False, tr("watched.score.status.not_selected")

    dataset_key, _movie, _card = entry
    if str(dataset_key).strip() == "":
        return False, tr("watched.score.status.not_selected")

    return True, ""
