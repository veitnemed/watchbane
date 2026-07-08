from __future__ import annotations

from storage.sqlite import candidate_repository


def test_candidate_repository_facade_exports_public_api() -> None:
    assert set(candidate_repository.__all__) == {
        "clear_candidate_pool",
        "get_worst_candidate_records",
        "load_candidate_criteria_dict",
        "load_candidate_pool_dict",
        "query_candidate_records",
        "save_candidate_criteria_dict",
        "save_candidate_pool_dict",
    }


def _empty_watched(monkeypatch) -> None:
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})


def test_candidate_pool_roundtrip_preserves_shape(tmp_path, monkeypatch) -> None:
    _empty_watched(monkeypatch)
    db_path = tmp_path / "watchbane.sqlite3"
    pool = {
        "legacy": {
            "title": "Severance",
            "year": "2022",
            "media_type": "tv",
            "tmdb_id": "95396",
            "tmdb_score": "8.2",
            "tmdb_votes": "1000",
        }
    }

    candidate_repository.save_candidate_pool_dict(pool, path=db_path)

    loaded = candidate_repository.load_candidate_pool_dict(path=db_path)
    assert list(loaded) == ["severance|2022"]
    assert loaded["severance|2022"]["title"] == "Severance"
    assert loaded["severance|2022"]["year"] == 2022
    assert loaded["severance|2022"]["criteria_name"] == "pool"


def test_candidate_criteria_roundtrip(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    criteria = {"pool": {"country": "US", "genres": ["drama"], "count": 50}}

    candidate_repository.save_candidate_criteria_dict(criteria, path=db_path)

    assert candidate_repository.load_candidate_criteria_dict(path=db_path) == criteria


def test_candidate_pool_dedupe_keeps_best_candidate(tmp_path, monkeypatch) -> None:
    _empty_watched(monkeypatch)
    db_path = tmp_path / "watchbane.sqlite3"
    pool = {
        "low": {"title": "Dark", "year": 2017, "final_score": 1},
        "high": {"title": "Dark", "year": 2017, "final_score": 9},
    }

    candidate_repository.save_candidate_pool_dict(pool, path=db_path)

    loaded = candidate_repository.load_candidate_pool_dict(path=db_path)
    assert list(loaded) == ["dark|2017"]
    assert loaded["dark|2017"]["final_score"] == 9


def test_candidate_query_normalizes_media_type_alias(tmp_path, monkeypatch) -> None:
    _empty_watched(monkeypatch)
    db_path = tmp_path / "watchbane.sqlite3"
    candidate_repository.save_candidate_pool_dict(
        {"k": {"title": "Heat", "year": 1995, "media_type": "movie", "final_score": 9}},
        path=db_path,
    )

    results = candidate_repository.query_candidate_records(media_type="film", path=db_path)

    assert [candidate["title"] for candidate in results] == ["Heat"]


def test_candidate_pool_unicode_identity(tmp_path, monkeypatch) -> None:
    _empty_watched(monkeypatch)
    db_path = tmp_path / "watchbane.sqlite3"

    candidate_repository.save_candidate_pool_dict(
        {"k": {"title": "Ёлки", "year": 2010, "media_type": "movie"}},
        path=db_path,
    )

    assert "елки|2010" in candidate_repository.load_candidate_pool_dict(path=db_path)


def test_clear_candidate_pool_keeps_criteria(tmp_path, monkeypatch) -> None:
    _empty_watched(monkeypatch)
    db_path = tmp_path / "watchbane.sqlite3"
    candidate_repository.save_candidate_pool_dict({"k": {"title": "Dark", "year": 2017}}, path=db_path)
    candidate_repository.save_candidate_criteria_dict({"pool": {"count": 10}}, path=db_path)

    candidate_repository.clear_candidate_pool(path=db_path)

    assert candidate_repository.load_candidate_pool_dict(path=db_path) == {}
    assert candidate_repository.load_candidate_criteria_dict(path=db_path) == {"pool": {"count": 10}}


def test_candidate_pool_save_respects_external_transaction(tmp_path, monkeypatch) -> None:
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations

    _empty_watched(monkeypatch)
    db_path = tmp_path / "watchbane.sqlite3"
    conn = connect(db_path)
    apply_migrations(conn)
    try:
        conn.execute("BEGIN")
        candidate_repository.save_candidate_pool_dict(
            {"k": {"title": "Dark", "year": 2017}},
            conn=conn,
        )
        conn.rollback()
    finally:
        conn.close()

    assert candidate_repository.load_candidate_pool_dict(path=db_path) == {}
