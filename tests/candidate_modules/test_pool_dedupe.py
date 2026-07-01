"""Tests for pool deduplication."""

from candidates.pool.dedupe import deduplicate_pool


def test_deduplicate_pool_keeps_best_score() -> None:
    pool = {
        "a": {"title": "Show", "year": 2018, "kp_score": 7.0, "criteria_name": "pool"},
        "b": {"title": "Show", "year": 2018, "kp_score": 8.5, "criteria_name": "pool"},
    }
    deduped = deduplicate_pool(pool)
    assert len(deduped) == 1
    assert list(deduped.values())[0]["kp_score"] == 8.5


def test_deduplicate_pool_does_not_merge_different_years() -> None:
    pool = {
        "a": {"title": "Show", "year": 2018, "kp_score": 7.0, "criteria_name": "pool"},
        "b": {"title": "Show", "year": 2019, "kp_score": 8.5, "criteria_name": "pool"},
    }
    deduped = deduplicate_pool(pool)
    assert len(deduped) == 2
