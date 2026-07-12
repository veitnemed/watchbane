"""Tests for the deck reserve indicator widget."""

from __future__ import annotations

from candidates.deck_reserve_presentation import DeckReservePresentation
from candidates.recommendation_deck_service import compute_deck_reserve_snapshot

from desktop.candidates.deck_reserve_indicator import DeckReserveIndicator, _progress_color


def _ready_deck(active_count: int = 18) -> dict:
    return {
        "active_limit": 25,
        "active": [{}] * active_count,
        "reserve": [],
    }


def test_progress_color_interpolates_red_to_green() -> None:
    low = _progress_color(0.0)
    mid = _progress_color(0.5)
    high = _progress_color(1.0)
    assert low.red() > mid.red() > 0 or low.red() >= mid.red()
    assert high.green() > low.green()
    assert high.green() >= mid.green() >= low.green()


def test_apply_presentation_ready_shows_percent(qtbot) -> None:
    indicator = DeckReserveIndicator()
    qtbot.addWidget(indicator)
    snapshot = compute_deck_reserve_snapshot(_ready_deck(active_count=18))
    indicator.apply_presentation(
        DeckReservePresentation(
            mode="ready",
            snapshot=snapshot,
            tooltip_key="recommendations.deck_reserve.tooltip",
            tooltip_kwargs={"remaining": snapshot.remaining, "target": snapshot.target},
        )
    )
    assert indicator.isVisible()
    assert indicator.progress() == snapshot.ratio


def test_apply_presentation_loading_hides_percent(qtbot) -> None:
    indicator = DeckReserveIndicator()
    qtbot.addWidget(indicator)
    indicator.apply_presentation(
        DeckReservePresentation(
            mode="loading",
            tooltip_key="recommendations.deck_reserve.loading",
        )
    )
    assert indicator.isVisible()
    assert indicator.progress() == 0.0


def test_apply_presentation_idle_hides_widget(qtbot) -> None:
    indicator = DeckReserveIndicator()
    qtbot.addWidget(indicator)
    indicator.apply_presentation(DeckReservePresentation(mode="idle"))
    assert indicator.isHidden()
