from __future__ import annotations

from storage.sqlite import candidate_repository, watched_repository


def _candidate(index: int) -> dict:
    return {
        "title": f"Candidate {index}",
        "year": 2000 + (index % 25),
        "media_type": "movie" if index % 2 == 0 else "tv",
        "tmdb_id": index,
        "tmdb_score": float(index % 10),
        "tmdb_votes": 100 + index,
        "tmdb_popularity": float(index),
        "quality_score": float(index % 100),
        "hidden_gem_score": float(index % 50),
        "final_score": float(index % 100),
        "criteria_name": "pool",
    }


def test_candidate_indexed_filter_query_returns_correct_subset(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    pool = {f"k{index}": _candidate(index) for index in range(1200)}
    candidate_repository.save_candidate_pool_dict(pool, path=db_path, purge_watched=False)

    rows = candidate_repository.query_candidate_records(
        path=db_path,
        media_type="movie",
        min_year=2010,
        min_tmdb_score=7.0,
        min_final_score=50.0,
        limit=25,
    )

    assert 0 < len(rows) <= 25
    assert all(row["media_type"] == "movie" for row in rows)
    assert all(row["year"] >= 2010 for row in rows)
    assert all(row["tmdb_score"] >= 7.0 for row in rows)
    assert all(row["final_score"] >= 50.0 for row in rows)
    assert rows == sorted(rows, key=lambda item: (-item["final_score"], -item["quality_score"], -item["tmdb_score"], item["title"].casefold()))


def test_candidate_worst_query_uses_lowest_scores(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    pool = {f"k{index}": _candidate(index) for index in range(1000)}
    candidate_repository.save_candidate_pool_dict(pool, path=db_path, purge_watched=False)

    rows = candidate_repository.get_worst_candidate_records(path=db_path, limit=10)

    assert len(rows) == 10
    scores = [row["final_score"] for row in rows]
    assert scores == sorted(scores)
    assert scores[0] == 0.0


def test_watched_identity_lookup_uses_indexed_columns(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    watched_repository.save_dataset_dict(
        {
            "Watchmen": {
                "main_info": {
                    "title": "Watchmen",
                    "year": 2019,
                    "user_score": 8,
                    "country": "US",
                    "media_type": "tv",
                },
                "raw_scores": {"tmdb_id": 79788},
                "genre": {},
            },
            "Watchmen (2009, movie)": {
                "main_info": {
                    "title": "Watchmen",
                    "year": 2009,
                    "user_score": 8,
                    "country": "US",
                    "media_type": "movie",
                },
                "raw_scores": {"tmdb_id": 13183},
                "genre": {},
            },
        },
        path=db_path,
    )

    assert watched_repository.find_watched_identity("watchmen", year=2009, media_type="movie", path=db_path) == "Watchmen (2009, movie)"
    assert watched_repository.find_watched_identity("Watchmen", tmdb_id=79788, path=db_path) == "Watchmen"
