from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from candidates.models.keys import pool_entry_key
from storage.sqlite.candidate_pool_repository import (
    load_candidate_pool_dict,
    merge_candidate_pool_dict,
)
from storage.sqlite.recommendation_deck_repository import save_current_deck


def _candidate(index: int, *, score: float | None = None) -> dict:
    candidate = {
        "title": f"Candidate {index:04d}",
        "year": 2000 + index % 20,
        "media_type": "movie" if index % 2 else "tv",
        "tmdb_id": 50_000 + index,
        "final_score": float(index if score is None else score),
        "quality_score": float(index if score is None else score),
        "tmdb_score": 5.0,
    }
    candidate["pool_entry_key"] = pool_entry_key(candidate)
    return candidate


def test_concurrent_incremental_merges_do_not_lose_either_batch(tmp_path) -> None:
    db_path = tmp_path / "pool.sqlite3"
    first = {_candidate(index)["pool_entry_key"]: _candidate(index) for index in range(40)}
    second = {_candidate(index)["pool_entry_key"]: _candidate(index) for index in range(40, 80)}

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda batch: merge_candidate_pool_dict(batch, path=db_path), (first, second)))

    assert all(result["merged"] == 40 for result in results)
    assert len(load_candidate_pool_dict(path=db_path)) == 80


def test_merge_caps_pool_and_protects_current_deck(tmp_path) -> None:
    db_path = tmp_path / "pool.sqlite3"
    initial = {_candidate(index)["pool_entry_key"]: _candidate(index) for index in range(12)}
    merge_candidate_pool_dict(initial, path=db_path, max_records=20)
    protected = initial[_candidate(0)["pool_entry_key"]]
    save_current_deck(
        {
            "deck_id": "deck-1",
            "active": [protected],
            "reserve": [],
        },
        path=db_path,
    )
    incoming = {_candidate(index)["pool_entry_key"]: _candidate(index) for index in range(12, 25)}

    result = merge_candidate_pool_dict(incoming, path=db_path, max_records=20)
    pool = load_candidate_pool_dict(path=db_path)

    assert result == {"merged": 13, "evicted": 5, "pool_size": 20}
    assert protected["pool_entry_key"] in pool
    assert set(incoming).issubset(pool)


def test_merge_failure_rolls_back_upserts_and_eviction(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "pool.sqlite3"
    initial = {_candidate(index)["pool_entry_key"]: _candidate(index) for index in range(12)}
    merge_candidate_pool_dict(initial, path=db_path, max_records=12)
    before = load_candidate_pool_dict(path=db_path)
    incoming = {_candidate(index)["pool_entry_key"]: _candidate(index) for index in range(12, 20)}

    def fail_fts_rebuild(_conn) -> None:
        raise RuntimeError("synthetic interruption before commit")

    monkeypatch.setattr(
        "storage.sqlite.candidate_pool_repository.rebuild_fts_index",
        fail_fts_rebuild,
    )

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        merge_candidate_pool_dict(incoming, path=db_path, max_records=12)

    assert load_candidate_pool_dict(path=db_path) == before
