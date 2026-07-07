"""Watched user_score write helpers (no Qt)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from desktop.i18n import tr
from desktop.watched.model.filters import USER_SCORE_MIN
from desktop.watched.model.load import WatchedEntry


def normalize_user_score_value(score) -> float:
    """Normalize user score to one decimal place for storage/display."""
    return float(Decimal(str(float(score))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def get_user_score_spin_value(card: dict) -> float:
    """Return user_score formatted for QDoubleSpinBox."""
    score = card.get("user_score")
    if score is None:
        return USER_SCORE_MIN
    return normalize_user_score_value(score)


def build_user_score_update_payload(user_score: float) -> dict:
    """Build update_dataset_record patch for user_score only."""
    return {"main_info": {"user_score": normalize_user_score_value(user_score)}}


def save_watched_user_score(dataset_key: str, user_score: float):
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
