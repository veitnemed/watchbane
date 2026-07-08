from __future__ import annotations

from storage.sqlite import watched_repository


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
        "tags_vibe": {},
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
