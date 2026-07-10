"""Computed score assembly for watched records."""

from common import format_score


def build_computed_scores(raw_scores: dict, main_info: dict) -> dict:
    """Build computed_scores from raw_scores and main_info."""
    return format_score.raw_to_struct(raw_scores, main_info)
