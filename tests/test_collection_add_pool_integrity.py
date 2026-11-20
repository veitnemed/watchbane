from contextlib import closing

import pytest

from candidates.models.keys import pool_entry_key
from candidates.search.fts_index import inspect_fts_index, rebuild_fts_index
from dataset.add_flow.save import save_add_title_record
from storage import data
from storage.sqlite.candidate_pool_repository import (
    load_candidate_pool_dict,
    merge_candidate_pool_dict,
)
from storage.sqlite.candidate_write import insert_candidate_record
from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations
from storage.sqlite.session import utc_now


def _pool_title(title, tmdb_id=None, media_type="movie"):
    return {"title": title, "year": 2022, "media_type": media_type, "tmdb_id": tmdb_id,
            "tmdb_score": 8.0, "final_score": 8.0}


def _watched_defaults(title="Alpha"):
    return {
        "main_info": {"title": title, "year": 2022, "media_type": "movie"},
        "raw_scores": {"tmdb_score": 8.0, "tmdb_votes": 1000},
    }


@pytest.fixture(autouse=True)
def isolated_profile(monkeypatch, tmp_path):
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("posters.cache.sync_poster_cache_from_meta_and_sources", lambda *a, **kw: {})
    monkeypatch.setattr("posters.download_images.download_poster_for_title", lambda *a, **kw: {"ok": True})


def _seed(*entries):
    # Give legacy homonyms distinct persisted keys before testing the add
    # path. Unrelated bulk import normalization is outside this regression.
    with closing(connect()) as conn:
        apply_migrations(conn)
        with conn:
            for index, candidate in enumerate(entries):
                insert_candidate_record(
                    conn, pool_key=f"legacy-fixture-{index}", candidate=candidate, timestamp=utc_now()
                )
            rebuild_fts_index(conn)


def _identities():
    return {(record["media_type"], record.get("tmdb_id")) for record in load_candidate_pool_dict().values()}


@pytest.mark.parametrize("explicit_candidate", [False, True])
def test_live_collection_add_never_replaces_the_candidate_pool(monkeypatch, explicit_candidate):
    from candidates.repositories import pool_repository

    selected = _pool_title("An alternate title for Alpha", 101)
    homonym = _pool_title("Alpha", 202)
    different_type = _pool_title("Alpha", 101, "tv")
    not_validated = _pool_title("Alpha")
    refill = _pool_title("Unrelated refill", 303)
    _seed(selected, homonym, different_type, not_validated)

    def poster_hook(*_args, **_kwargs):
        # Real post-commit refill, before the former whole-pool copy/save.
        merge_candidate_pool_dict({pool_entry_key(refill): refill})
        return {"ok": True}

    class ForbiddenBulkCall(Exception):
        pass

    calls = []

    def stop_bulk_write(_):
        calls.append(True)
        raise ForbiddenBulkCall()

    monkeypatch.setattr("posters.download_images.download_poster_for_title", poster_hook)
    monkeypatch.setattr(pool_repository, "save_candidate_pool", stop_bulk_write)
    outcome = save_add_title_record(
        _watched_defaults(), 2, meta_payload={"tmdb_id": 101},
        pool_candidate=selected if explicit_candidate else None,
    )
    assert outcome.ok
    assert calls == []
    assert _identities() == {("movie", 202), ("tv", 101), ("movie", None), ("movie", 303)}
    assert data.load_meta()[outcome.title]["tmdb_id"] == 101
    with closing(connect()) as conn:
        assert inspect_fts_index(conn)["ok"]


def test_idless_collection_add_does_not_purge_titles_by_name():
    _seed(_pool_title("Alpha", 101), _pool_title("Alpha"))
    assert save_add_title_record(_watched_defaults(), 2).ok
    assert _identities() == {("movie", 101), ("movie", None)}


def test_pool_write_failure_rolls_back_watched_insert_and_fts():
    selected = _pool_title("Alpha", 101)
    _seed(selected)
    with closing(connect()) as conn, conn:
        conn.execute("""
            CREATE TRIGGER failed_pool_delete BEFORE DELETE ON candidate_records
            BEGIN SELECT RAISE(ABORT, 'forced pool write failure'); END
        """)
    outcome = save_add_title_record(_watched_defaults(), 2, meta_payload={"tmdb_id": 101})
    assert not outcome.ok and outcome.reason == "save_error"
    assert data.load_dataset() == {}
    assert _identities() == {("movie", 101)}
    with closing(connect()) as conn:
        assert inspect_fts_index(conn)["ok"]
