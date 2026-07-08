"""Tests for pool deduplication."""

from candidates.pool.dedupe import deduplicate_pool, dedupe_pool_by_similar_titles, normalized_title_key


def test_deduplicate_pool_keeps_best_score() -> None:
    pool = {
        "a": {"title": "Show", "year": 2018, "tmdb_score": 7.0, "tmdb_votes": 100, "criteria_name": "pool"},
        "b": {"title": "Show", "year": 2018, "tmdb_score": 8.5, "tmdb_votes": 200, "criteria_name": "pool"},
    }
    deduped = deduplicate_pool(pool)
    assert len(deduped) == 1
    assert list(deduped.values())[0]["tmdb_score"] == 8.5


def test_deduplicate_pool_does_not_merge_different_years() -> None:
    pool = {
        "a": {"title": "Show", "year": 2018, "tmdb_score": 7.0, "criteria_name": "pool"},
        "b": {"title": "Show", "year": 2019, "tmdb_score": 8.5, "criteria_name": "pool"},
    }
    deduped = deduplicate_pool(pool)
    assert len(deduped) == 2


def test_normalized_title_key_uses_shared_key_normalization() -> None:
    assert normalized_title_key("\u00abНадёжный метод\u00bb!") == "надежный метод"


def test_similar_dedupe_merges_russian_yo_variant() -> None:
    pool = {
        "a": {"title": "Надёжный метод", "year": 2018, "tmdb_score": 7.0, "criteria_name": "pool"},
        "b": {"title": "Надежный метод", "year": 2018, "tmdb_score": 8.5, "criteria_name": "pool"},
    }

    deduped, removed = dedupe_pool_by_similar_titles(pool)

    assert removed == 1
    assert len(deduped) == 1
    assert list(deduped.values())[0]["tmdb_score"] == 8.5
