from __future__ import annotations

from storage.sqlite import watched_repository


def test_watched_repository_facade_exports_public_api() -> None:
    assert set(watched_repository.__all__) == {
        "delete_watched",
        "find_exact_title",
        "find_watched_identity",
        "get_meta_obj",
        "is_origin_title",
        "load_dataset_dict",
        "load_meta_dict",
        "save_dataset_dict",
        "save_meta_dict",
    }


def _movie(title: str = "Метод", *, media_type: str = "tv") -> dict:
    return {
        "main_info": {
            "title": title,
            "year": 2015,
            "country": "Россия",
            "user_score": 8.5,
            "media_type": media_type,
        },
        "raw_scores": {"tmdb_score": 7.4},
        "genre": {},
    }


def test_watched_dataset_roundtrip_preserves_legacy_shape(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    dataset = {"Метод": _movie()}

    watched_repository.save_dataset_dict(dataset, path=db_path)

    loaded = watched_repository.load_dataset_dict(path=db_path)
    assert loaded["Метод"]["main_info"]["title"] == "Метод"
    assert loaded["Метод"]["main_info"]["media_type"] == "tv"


def test_watched_meta_roundtrip_and_lookup(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    meta = {"Метод": {"main_info": {"title": "Метод"}, "raw_scores": {"tmdb_id": 693}}}

    watched_repository.save_meta_dict(meta, path=db_path)

    assert watched_repository.load_meta_dict(path=db_path) == meta
    assert watched_repository.get_meta_obj(" метод ", path=db_path)["raw_scores"]["tmdb_id"] == 693


def test_dataset_and_meta_saves_do_not_delete_each_other(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"

    watched_repository.save_dataset_dict({"Метод": _movie()}, path=db_path)
    watched_repository.save_meta_dict({"Метод": {"raw_scores": {"tmdb_id": 693}}}, path=db_path)
    watched_repository.save_dataset_dict({"Метод": _movie()}, path=db_path)

    assert "Метод" in watched_repository.load_dataset_dict(path=db_path)
    assert watched_repository.load_meta_dict(path=db_path)["Метод"]["raw_scores"]["tmdb_id"] == 693

    watched_repository.save_meta_dict({}, path=db_path)
    assert "Метод" in watched_repository.load_dataset_dict(path=db_path)
    assert watched_repository.load_meta_dict(path=db_path) == {}


def test_find_exact_title_origin_and_delete(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    watched_repository.save_dataset_dict({"Watchmen": _movie("Watchmen", media_type="movie")}, path=db_path)

    assert watched_repository.find_exact_title("watchmen", path=db_path) == "Watchmen"
    assert watched_repository.is_origin_title("WATCHMEN", path=db_path) is False

    watched_repository.delete_watched("Watchmen", path=db_path)

    assert watched_repository.load_dataset_dict(path=db_path) == {}
    assert watched_repository.is_origin_title("Watchmen", path=db_path) is True


def test_find_watched_identity_normalizes_media_type_alias(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    watched_repository.save_dataset_dict({"Watchmen": _movie("Watchmen", media_type="movie")}, path=db_path)

    assert (
        watched_repository.find_watched_identity(
            " watchmen ",
            year=2015,
            media_type="film",
            path=db_path,
        )
        == "Watchmen"
    )


def test_delete_watched_preserves_meta(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    watched_repository.save_dataset_dict({"Метод": _movie()}, path=db_path)
    watched_repository.save_meta_dict({"Метод": {"raw_scores": {"tmdb_id": 693}}}, path=db_path)

    watched_repository.delete_watched("Метод", path=db_path)

    assert watched_repository.load_dataset_dict(path=db_path) == {}
    assert watched_repository.load_meta_dict(path=db_path) == {"Метод": {"raw_scores": {"tmdb_id": 693}}}


def test_clear_legacy_meta_removes_indexed_identity_without_losing_watched_rating(tmp_path):
    from contextlib import closing
    from storage.sqlite.connection import connect

    db = tmp_path / "watched.sqlite3"
    dataset = {"Observed": _movie("Observed", media_type="movie"),
               "Explicit": _movie("Explicit", media_type="movie")}
    dataset["Explicit"]["raw_scores"].update(tmdb_id=200, imdb_id="tt1234500")
    watched_repository.save_dataset_dict(dataset, path=db)
    watched_repository.save_meta_dict({
        "Observed": {"raw_scores": {"tmdb_id": 100, "imdb_id": "tt1234400"}},
        "Explicit": {"raw_scores": {"tmdb_id": 200, "imdb_id": "tt1234500"}},
        "Meta only": {"raw_scores": {"tmdb_id": 300}},
    }, path=db)
    assert watched_repository.find_watched_identity("Observed", tmdb_id=100, path=db) == "Observed"

    with closing(connect(db)) as conn:
        before = dict(conn.execute("SELECT * FROM watched_records WHERE dataset_key = 'Observed'").fetchone())
    watched_repository.save_meta_dict({}, path=db)

    assert watched_repository.find_watched_identity("Observed", tmdb_id=100, path=db) is None
    assert watched_repository.find_watched_identity("Observed", media_type="movie", year=2015, path=db) == "Observed"
    assert watched_repository.find_watched_identity("Explicit", tmdb_id=200, path=db) == "Explicit"
    with closing(connect(db)) as conn:
        after = dict(conn.execute("SELECT * FROM watched_records WHERE dataset_key = 'Observed'").fetchone())
        assert after["tmdb_id"] is None and after["imdb_id"] is None
        assert after["payload_json"] == before["payload_json"]
        assert after["created_at"] == before["created_at"] and after["user_score"] == before["user_score"]
        assert conn.execute("SELECT COUNT(*) FROM watched_records WHERE dataset_key = 'Meta only'").fetchone()[0] == 0


def test_payload_removal_reprojects_only_surviving_metadata(tmp_path):
    from contextlib import closing
    from storage.sqlite.connection import connect

    for mode in ("delete", "bulk omission"):
        db = tmp_path / (mode + ".sqlite3")
        watched_repository.save_dataset_dict({"legacy": {
            "main_info": {"title":"Deleted film", "media_type":"movie", "year":2001,
                          "country":"US", "user_score":3},
            "raw_scores": {"tmdb_id":100, "imdb_id":"tt0000100"},
        }}, path=db)
        watched_repository.save_meta_dict({"legacy": {
            "main_info": {"title":"Retained series", "media_type":"tv", "year":2020},
            "raw_scores": {"tmdb_id":200, "imdb_id":"tt0000200"},
        }}, path=db)
        def row():
            with closing(connect(db)) as conn:
                return dict(conn.execute("SELECT * FROM watched_records WHERE dataset_key='legacy'").fetchone())
        before = row()
        assert (before["media_type"], before["tmdb_id"], before["year"]) == ("movie", 100, 2001)
        if mode == "delete":
            watched_repository.delete_watched("legacy", path=db)
        else:
            watched_repository.save_dataset_dict({}, path=db)
        retained = row()
        assert retained["payload_json"] == "{}"
        assert retained["meta_json"] == before["meta_json"]
        assert retained["created_at"] == before["created_at"]
        assert (retained["title"], retained["media_type"], retained["year"]) == ("Retained series", "tv", 2020)
        assert (retained["tmdb_id"], retained["imdb_id"], retained["user_score"]) == (200, "tt0000200", None)


def test_payload_readd_can_reuse_only_matching_metadata_identity(tmp_path):
    from candidates.title_state_service import mark_watched

    db = tmp_path / "watched.sqlite3"
    watched_repository.save_dataset_dict({
        "historical": {"main_info": {"title":"Old", "media_type":"movie"},
                       "raw_scores":{"tmdb_id":100}},
    }, path=db)
    watched_repository.save_meta_dict({
        "historical": {"main_info":{"title":"Other", "media_type":"movie"},
                       "raw_scores":{"tmdb_id":200}},
    }, path=db)
    watched_repository.delete_watched("historical", path=db)

    old = mark_watched({"title":"Old", "media_type":"movie", "year":2020, "tmdb_id":100}, path=db)
    assert old["dataset_key"] != "historical"
    assert watched_repository.load_meta_dict(path=db)["historical"]["raw_scores"]["tmdb_id"] == 200
    new = mark_watched({"title":"Other", "media_type":"movie", "year":2020, "tmdb_id":200}, path=db)
    assert new["dataset_key"] == "historical"
    assert len(watched_repository.load_dataset_dict(path=db)) == 2
