"""Tests for deck reserve presentation resolution."""

from __future__ import annotations

from candidates.deck_reserve_presentation import resolve_deck_reserve_presentation
from candidates.recommendation_deck_service import ACTIVE_DECK_SIZE


def _ready_deck(active_count: int = 25, reserve_count: int = 0) -> dict:
    return {
        "active_limit": ACTIVE_DECK_SIZE,
        "active": [{}] * active_count,
        "reserve": [{}] * reserve_count,
    }


def test_idle_when_recommendations_inactive() -> None:
    presentation = resolve_deck_reserve_presentation(
        recommendations_active=False,
        deck=_ready_deck(),
        deck_build_in_progress=False,
        deck_load_scheduled=False,
        deck_prepare_active=False,
        session_loading=False,
        replenishing_for_deck=False,
        build_failed=False,
    )
    assert presentation.mode == "idle"
    assert presentation.snapshot is None


def test_loading_when_deck_none_and_build_in_progress() -> None:
    presentation = resolve_deck_reserve_presentation(
        recommendations_active=True,
        deck=None,
        deck_build_in_progress=True,
        deck_load_scheduled=False,
        deck_prepare_active=False,
        session_loading=False,
        replenishing_for_deck=False,
        build_failed=False,
    )
    assert presentation.mode == "loading"
    assert presentation.snapshot is None


def test_error_when_build_failed() -> None:
    presentation = resolve_deck_reserve_presentation(
        recommendations_active=True,
        deck=None,
        deck_build_in_progress=False,
        deck_load_scheduled=False,
        deck_prepare_active=False,
        session_loading=False,
        replenishing_for_deck=False,
        build_failed=True,
    )
    assert presentation.mode == "error"


def test_no_stale_snapshot_during_reload() -> None:
    presentation = resolve_deck_reserve_presentation(
        recommendations_active=True,
        deck=_ready_deck(active_count=25, reserve_count=70),
        deck_build_in_progress=True,
        deck_load_scheduled=False,
        deck_prepare_active=False,
        session_loading=False,
        replenishing_for_deck=False,
        build_failed=False,
    )
    assert presentation.mode == "loading"
    assert presentation.snapshot is None


def test_replenishing_hides_snapshot() -> None:
    presentation = resolve_deck_reserve_presentation(
        recommendations_active=True,
        deck=_ready_deck(active_count=25, reserve_count=70),
        deck_build_in_progress=False,
        deck_load_scheduled=False,
        deck_prepare_active=False,
        session_loading=True,
        replenishing_for_deck=False,
        build_failed=False,
    )
    assert presentation.mode == "replenishing"
    assert presentation.snapshot is None


def test_ready_returns_snapshot() -> None:
    presentation = resolve_deck_reserve_presentation(
        recommendations_active=True,
        deck=_ready_deck(active_count=7),
        deck_build_in_progress=False,
        deck_load_scheduled=False,
        deck_prepare_active=False,
        session_loading=False,
        replenishing_for_deck=False,
        build_failed=False,
    )
    assert presentation.mode == "ready"
    assert presentation.snapshot is not None
    assert presentation.snapshot.percent == 16


def test_offline_keeps_local_supply_visible() -> None:
    presentation = resolve_deck_reserve_presentation(
        recommendations_active=True,
        deck=_ready_deck(active_count=7),
        deck_build_in_progress=False,
        deck_load_scheduled=False,
        deck_prepare_active=False,
        session_loading=False,
        replenishing_for_deck=False,
        build_failed=False,
        offline=True,
    )
    assert presentation.mode == "offline"
    assert presentation.snapshot is not None
    assert presentation.snapshot.remaining == 7
    assert presentation.tooltip_kwargs["remaining"] == 7
