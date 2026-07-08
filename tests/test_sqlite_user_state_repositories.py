from __future__ import annotations

from storage.sqlite import (
    action_repository,
    candidate_repository,
    poster_repository,
    settings_repository,
    watched_repository,
)


def test_hidden_and_watchlist_action_identities_roundtrip(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    candidate = {"title": "Метод", "year": 2015}

    hidden = action_repository.add_candidate_action(
        action_repository.ACTION_HIDDEN,
        candidate,
        path=db_path,
    )
    watchlist = action_repository.add_candidate_action(
        action_repository.ACTION_WATCHLIST,
        candidate,
        path=db_path,
    )

    assert hidden["identity"] == "метод|2015"
    assert watchlist["identity"] == "метод|2015"
    assert action_repository.load_action_identities(action_repository.ACTION_HIDDEN, path=db_path) == {"метод|2015"}
    assert action_repository.load_action_identities(action_repository.ACTION_WATCHLIST, path=db_path) == {"метод|2015"}


def test_candidate_actions_mapping_roundtrip(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    mapping = {
        "dark|2017": {
            "candidate": {"title": "Dark", "year": 2017},
            "hidden_at": "2026-01-01T00:00:00",
        }
    }

    action_repository.save_candidate_actions_dict(action_repository.ACTION_HIDDEN, mapping, path=db_path)

    assert action_repository.load_candidate_actions_dict(action_repository.ACTION_HIDDEN, path=db_path) == mapping


def test_candidate_action_add_respects_external_transaction(tmp_path) -> None:
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations

    db_path = tmp_path / "watchbane.sqlite3"
    conn = connect(db_path)
    apply_migrations(conn)
    try:
        conn.execute("BEGIN")
        action_repository.add_candidate_action(
            action_repository.ACTION_HIDDEN,
            {"title": "Dark", "year": 2017},
            conn=conn,
        )
        conn.rollback()
    finally:
        conn.close()

    assert action_repository.load_candidate_actions_dict(action_repository.ACTION_HIDDEN, path=db_path) == {}


def test_settings_roundtrip(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    settings_repository.save_settings_dict({"ui_scale": 1.25, "flags": {"a": True}}, path=db_path)
    settings_repository.set_setting("theme", "dark", path=db_path)

    loaded = settings_repository.load_settings_dict(path=db_path)
    assert loaded["ui_scale"] == 1.25
    assert loaded["flags"] == {"a": True}
    assert settings_repository.get_setting("theme", path=db_path) == "dark"
    assert settings_repository.get_setting("missing", "fallback", path=db_path) == "fallback"


def test_setting_set_respects_external_transaction(tmp_path) -> None:
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations

    db_path = tmp_path / "watchbane.sqlite3"
    conn = connect(db_path)
    apply_migrations(conn)
    try:
        conn.execute("BEGIN")
        settings_repository.set_setting("theme", "dark", conn=conn)
        conn.rollback()
    finally:
        conn.close()

    assert settings_repository.load_settings_dict(path=db_path) == {}


def test_poster_metadata_roundtrip_and_lookup(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    cache = {
        "метод|2015": {
            "title": "Метод",
            "year": 2015,
            "poster_path": "/a.jpg",
            "poster_url": "https://example.test/a.jpg",
            "local_path": "data/cache/posters/images/method.jpg",
            "status": "found",
            "source": "test",
            "updated_at": "2026-01-01T00:00:00",
        }
    }

    poster_repository.save_poster_cache_dict(cache, path=db_path)

    assert poster_repository.load_poster_cache_dict(path=db_path) == cache
    assert poster_repository.lookup_poster_cache_entry("Метод", 2015, path=db_path)["status"] == "found"


def test_poster_metadata_upsert_does_not_store_image_bytes(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"

    entry = poster_repository.upsert_poster_cache_entry(
        "Dark",
        2017,
        {
            "poster_path": "/dark.jpg",
            "poster_url": "https://example.test/dark.jpg",
            "local_path": "data/cache/posters/images/dark.jpg",
            "status": "found",
            "source": "test",
        },
        path=db_path,
    )

    assert entry["local_path"].endswith("dark.jpg")
    assert "image_bytes" not in entry
    assert poster_repository.lookup_poster_cache_entry("Dark", 2017, path=db_path)["poster_path"] == "/dark.jpg"


def test_poster_upsert_respects_external_transaction(tmp_path) -> None:
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations

    db_path = tmp_path / "watchbane.sqlite3"
    conn = connect(db_path)
    apply_migrations(conn)
    try:
        conn.execute("BEGIN")
        poster_repository.upsert_poster_cache_entry(
            "Dark",
            2017,
            {"poster_path": "/dark.jpg", "status": "found"},
            conn=conn,
        )
        conn.rollback()
    finally:
        conn.close()

    assert poster_repository.lookup_poster_cache_entry("Dark", 2017, path=db_path) is None


def test_external_transaction_rolls_back_multiple_repositories(tmp_path, monkeypatch) -> None:
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations

    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    db_path = tmp_path / "watchbane.sqlite3"
    conn = connect(db_path)
    apply_migrations(conn)
    try:
        conn.execute("BEGIN")
        watched_repository.save_dataset_dict(
            {
                "Dark": {
                    "main_info": {
                        "title": "Dark",
                        "year": 2017,
                        "user_score": 8,
                        "country": "DE",
                        "media_type": "tv",
                    },
                    "raw_scores": {},
                }
            },
            conn=conn,
        )
        candidate_repository.save_candidate_pool_dict(
            {"dark": {"title": "Dark", "year": 2017}},
            conn=conn,
            purge_watched=False,
        )
        settings_repository.set_setting("theme", "dark", conn=conn)
        action_repository.add_candidate_action(
            action_repository.ACTION_HIDDEN,
            {"title": "Dark", "year": 2017},
            conn=conn,
        )
        poster_repository.upsert_poster_cache_entry(
            "Dark",
            2017,
            {"poster_path": "/dark.jpg", "status": "found"},
            conn=conn,
        )
        conn.rollback()
    finally:
        conn.close()

    assert watched_repository.load_dataset_dict(path=db_path) == {}
    assert candidate_repository.load_candidate_pool_dict(path=db_path) == {}
    assert settings_repository.load_settings_dict(path=db_path) == {}
    assert action_repository.load_candidate_actions_dict(action_repository.ACTION_HIDDEN, path=db_path) == {}
    assert poster_repository.lookup_poster_cache_entry("Dark", 2017, path=db_path) is None
