from __future__ import annotations

from candidates.pool.storage import build_tmdb_id_index, find_candidate_storage_match


def test_tmdb_id_index_is_scoped_by_media_type() -> None:
    pool = {
        "tv": {"title": "Show", "year": 2020, "media_type": "tv", "tmdb_id": "42"},
        "movie": {"title": "Movie", "year": 2021, "media_type": "movie", "tmdb_id": 42},
    }

    assert build_tmdb_id_index(pool) == {
        ("tv", 42): "tv",
        ("movie", 42): "movie",
    }


def test_candidate_storage_match_does_not_merge_same_tmdb_id_different_media_type() -> None:
    pool = {
        "tv": {"title": "Show", "year": 2020, "media_type": "tv", "tmdb_id": 42},
    }

    match, reason = find_candidate_storage_match(
        pool,
        {"title": "Movie", "year": 2021, "media_type": "movie", "tmdb_id": 42},
    )

    assert match is None
    assert reason is None


def test_candidate_storage_match_normalizes_media_type_aliases_for_tmdb_id() -> None:
    pool = {
        "tv": {"title": "Show", "year": 2020, "media_type": "series", "tmdb_id": 42},
    }

    match, reason = find_candidate_storage_match(
        pool,
        {"title": "Show", "year": 2020, "media_type": "tv_show", "tmdb_id": "42"},
    )

    assert match == "tv"
    assert reason == "tmdb_id"
