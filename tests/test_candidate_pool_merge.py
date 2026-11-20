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


def _homonym(identifier, *, title="Shared title", media_type="movie", overview="plot"):
    return {
        "title": title, "year": 2023, "tmdb_id": identifier, "media_type": media_type,
        "tmdb_score": 8, "tmdb_votes": 1000, "overview": overview,
    }


@pytest.mark.parametrize("same_batch", [True, False])
def test_incremental_merge_preserves_two_known_homonyms_and_fts(tmp_path, same_batch):
    from contextlib import closing

    from candidates.search.fts_index import inspect_fts_index
    from storage.sqlite.connection import connect

    db = tmp_path / "pool.sqlite3"
    first, second = (_homonym(101, overview="underwater exploration"),
                     _homonym(202, overview="mountain rescue"))
    if same_batch:
        assert merge_candidate_pool_dict({"first": first, "second": second}, path=db)["merged"] == 2
    else:
        merge_candidate_pool_dict({"first": first}, path=db)
        merge_candidate_pool_dict({"second": second}, path=db)
    pool = load_candidate_pool_dict(path=db)
    assert len(pool) == 2
    assert pool[pool_entry_key(first)]["tmdb_id"] == 101
    assert all(key == movie["pool_entry_key"] for key, movie in pool.items())
    with closing(connect(db)) as conn:
        assert inspect_fts_index(conn)["ok"]


def test_incremental_merge_detects_existing_typed_id_and_preserves_opaque_storage_key(tmp_path):
    from contextlib import closing

    from storage.sqlite.candidate_write import insert_candidate_record
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations

    db = tmp_path / "pool.sqlite3"
    existing = {**_homonym(101), "runtime": 98, "details_enrichment_status": "success"}
    with closing(connect(db)) as conn:
        apply_migrations(conn)
        with conn:
            insert_candidate_record(conn, pool_key="opaque:legacy:101", candidate=existing, timestamp="original")
    alias = _homonym(101, title="Localized alias")
    other_media = _homonym(101, title="Localized alias", media_type="tv")
    merge_candidate_pool_dict({"alias": alias, "other media": other_media}, path=db)
    pool = load_candidate_pool_dict(path=db)
    assert set(pool) == {"opaque:legacy:101", pool_entry_key(other_media)}
    assert pool["opaque:legacy:101"]["title"] == "Localized alias"
    assert pool["opaque:legacy:101"]["runtime"] == 98
    assert pool["opaque:legacy:101"]["pool_entry_key"] == "opaque:legacy:101"
    with closing(connect(db)) as conn:
        assert conn.execute(
            "SELECT created_at FROM candidate_records WHERE pool_key = 'opaque:legacy:101'"
        ).fetchone()[0] == "original"


@pytest.mark.parametrize("known_first", [True, False])
def test_incremental_known_and_idless_homonyms_do_not_overwrite_either(tmp_path, known_first):
    from contextlib import closing

    from storage.sqlite.connection import connect

    db = tmp_path / "pool.sqlite3"
    known, legacy = _homonym(101), _homonym(None)
    ordered = (known, legacy) if known_first else (legacy, known)
    for item in ordered:
        merge_candidate_pool_dict({"same": item}, path=db)
    first_pool = load_candidate_pool_dict(path=db)
    assert {v["tmdb_id"] for v in first_pool.values()} == {101, None}
    legacy_key = next(k for k, value in first_pool.items() if value["tmdb_id"] is None)
    # Even after the known row no longer occupies the shared title key,
    # reuse the existing legacy key when the next ID-less batch arrives.
    with closing(connect(db)) as conn, conn:
        conn.execute("DELETE FROM candidate_records WHERE tmdb_id = 101")
    merge_candidate_pool_dict({"same": {**legacy, "overview": "updated"}}, path=db)
    assert list(load_candidate_pool_dict(path=db)) == [legacy_key]


def test_onboarding_incremental_batch_does_not_collapse_ids_before_writer(tmp_path):
    from candidates.onboarding.autofill import _save_pool_incremental

    db = tmp_path / "pool.sqlite3"
    in_memory = {}
    _save_pool_incremental(in_memory, [_homonym(101), _homonym(202)], path=db)
    assert {row["tmdb_id"] for row in in_memory.values()} == {101, 202}
    assert in_memory == load_candidate_pool_dict(path=db)


def test_concurrent_homonym_refills_preserve_distinct_ids(tmp_path):
    db = tmp_path / "pool.sqlite3"
    batches = [{"same_key": _homonym(identifier)} for identifier in (101, 202)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda batch: merge_candidate_pool_dict(batch, path=db), batches))
    assert [result["merged"] for result in results] == [1, 1]
    assert {row["tmdb_id"] for row in load_candidate_pool_dict(path=db).values()} == {101, 202}



def test_merge_cap_protects_only_the_typed_saved_homonym(tmp_path):
    from candidates.models.keys import candidate_typed_state_key
    from storage.sqlite.action_repository import save_candidate_actions_dict

    db = tmp_path / "pool.sqlite3"
    saved = {**_homonym(101), "final_score": 1}
    other = {**_homonym(202), "final_score": 2}
    newcomer = {**_homonym(303, title="High-ranked arrival"), "final_score": 20}
    merge_candidate_pool_dict({"saved": saved, "other": other}, path=db, max_records=2)
    save_candidate_actions_dict("watchlist", {candidate_typed_state_key(saved): saved}, path=db)
    result = merge_candidate_pool_dict({"new": newcomer}, path=db, max_records=2)
    assert result["evicted"] == 1
    assert {row["tmdb_id"] for row in load_candidate_pool_dict(path=db).values()} == {101, 303}
