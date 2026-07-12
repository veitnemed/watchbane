"""Resolve deck reserve indicator presentation from deck data and UI flags."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from candidates.recommendation_deck_service import (
    DeckReserveSnapshot,
    compute_deck_reserve_snapshot,
)


@dataclass(frozen=True)
class DeckReservePresentation:
    mode: Literal["idle", "loading", "replenishing", "error", "offline", "ready"]
    snapshot: DeckReserveSnapshot | None = None
    tooltip_key: str | None = None
    tooltip_kwargs: dict = field(default_factory=dict)


def resolve_deck_reserve_presentation(
    *,
    recommendations_active: bool,
    deck: dict | None,
    deck_build_in_progress: bool,
    deck_load_scheduled: bool,
    deck_prepare_active: bool,
    session_loading: bool,
    replenishing_for_deck: bool,
    build_failed: bool,
    offline: bool = False,
) -> DeckReservePresentation:
    if not recommendations_active:
        return DeckReservePresentation(mode="idle")

    if deck is None:
        if build_failed:
            return DeckReservePresentation(
                mode="error",
                tooltip_key="recommendations.state.local_error",
            )
        if deck_build_in_progress or deck_load_scheduled or deck_prepare_active:
            return DeckReservePresentation(
                mode="loading",
                tooltip_key="recommendations.deck_reserve.loading",
            )
        return DeckReservePresentation(mode="idle")

    if session_loading or replenishing_for_deck:
        return DeckReservePresentation(
            mode="replenishing",
            tooltip_key="recommendations.state.replenishing",
        )

    if deck_build_in_progress or deck_prepare_active:
        return DeckReservePresentation(
            mode="loading",
            tooltip_key="recommendations.deck_reserve.loading",
        )

    snapshot = compute_deck_reserve_snapshot(deck)
    if offline:
        return DeckReservePresentation(
            mode="offline",
            snapshot=snapshot,
            tooltip_key="recommendations.deck_reserve.offline",
            tooltip_kwargs={"remaining": snapshot.remaining},
        )
    if snapshot.remaining == 0:
        return DeckReservePresentation(
            mode="ready",
            snapshot=snapshot,
            tooltip_key=(
                "recommendations.deck_reserve.fallback"
                if snapshot.empty_reason == "recent_fallback"
                else "recommendations.deck_reserve.empty"
            ),
        )
    return DeckReservePresentation(
        mode="ready",
        snapshot=snapshot,
        tooltip_key="recommendations.deck_reserve.tooltip",
        tooltip_kwargs={"remaining": snapshot.remaining, "target": snapshot.target},
    )
