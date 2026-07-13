"""Tests for deck reserve snapshot computation."""

from __future__ import annotations

from candidates.recommendation_deck_service import (
    ACTIVE_DECK_SIZE,
    compute_deck_reserve_snapshot,
)


def _deck(*, active_count: int = 0, reserve_count: int = 0, **extra) -> dict:
    return {
        "active_limit": ACTIVE_DECK_SIZE,
        "active": [{"title": f"a{index}"} for index in range(active_count)],
        "reserve": [{"title": f"r{index}"} for index in range(reserve_count)],
        **extra,
    }


def test_full_deck_caps_display_at_target() -> None:
    snapshot = compute_deck_reserve_snapshot(_deck(active_count=25, reserve_count=70))
    assert snapshot.remaining == 95
    assert snapshot.target == 45
    assert snapshot.ratio == 1.0
    assert snapshot.display_count == 45
    assert snapshot.percent == 100
    assert snapshot.band == "ready"


def test_underfilled_examples() -> None:
    snapshot_18 = compute_deck_reserve_snapshot(_deck(active_count=18))
    assert snapshot_18.remaining == 18
    assert snapshot_18.percent == 40
    assert snapshot_18.band == "critical"

    snapshot_7 = compute_deck_reserve_snapshot(_deck(active_count=7))
    assert snapshot_7.percent == 16
    assert snapshot_7.band == "critical"

    snapshot_1 = compute_deck_reserve_snapshot(_deck(active_count=1))
    assert snapshot_1.percent == 2
    assert snapshot_1.band == "critical"


def test_band_boundaries() -> None:
    assert compute_deck_reserve_snapshot(_deck(active_count=25, reserve_count=20)).band == "ready"
    assert compute_deck_reserve_snapshot(_deck(active_count=25, reserve_count=19)).band == "low"
    assert compute_deck_reserve_snapshot(_deck(active_count=25)).band == "low"
    assert compute_deck_reserve_snapshot(_deck(active_count=24)).band == "critical"


def test_fresh_eligible_candidates_extend_materialized_supply() -> None:
    snapshot = compute_deck_reserve_snapshot(
        _deck(active_count=10, reserve_count=5, catalog_eligible_count=60)
    )
    assert snapshot.fresh_eligible == 45
    assert snapshot.remaining == 60
    assert snapshot.band == "ready"


def test_empty_states() -> None:
    processed = compute_deck_reserve_snapshot(_deck(last_action={"action": "watched"}))
    assert processed.remaining == 0
    assert processed.band == "empty"
    assert processed.empty_reason == "processed"

    pool_empty = compute_deck_reserve_snapshot(_deck())
    assert pool_empty.band == "empty"
    assert pool_empty.empty_reason == "pool_empty"
    assert pool_empty.percent == 0

    fallback = compute_deck_reserve_snapshot(
        _deck(excluded={"recently_seen": 3})
    )
    assert fallback.empty_reason == "recent_fallback"
