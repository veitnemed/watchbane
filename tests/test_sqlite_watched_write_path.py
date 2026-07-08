from __future__ import annotations

from config import constant
from config import scheme
from common import format_score
from storage import data as storage_data


def _use_sqlite(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    watched_dir = data_dir / "watched"
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    monkeypatch.setattr("config.constant.WATCHED_DIR", str(watched_dir))
    monkeypatch.setattr("config.constant.FILE_NAME", str(watched_dir / "titles.json"))
    monkeypatch.setattr("config.constant.META_JSON", str(watched_dir / "meta.json"))
    monkeypatch.setenv("WATCHBANE_STORAGE_BACKEND", "sqlite")


def _movie(title: str = "Метод", *, user_score: float = 8.0, year: int = 2015) -> dict:
    main_info = {
        "title": title,
        "year": year,
        "user_score": user_score,
        "country": "Россия",
        "media_type": "tv",
    }
    raw_scores = {
        "tmdb_score": 8.0,
        "tmdb_votes": 1000,
        "tmdb_popularity": 42.5,
    }
    return {
        "main_info": main_info,
        "raw_scores": raw_scores,
        "computed_scores": format_score.raw_to_struct(raw_scores, main_info),
        scheme.TAGS_VIBE: {feature: 0 for feature in constant.TAGS_VIBE},
        constant.GENRE_SECTION: {feature: 0 for feature in constant.GENRE},
    }


def test_sqlite_backend_routes_save_and_clean_dataset_meta(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)

    storage_data.save_dataset({"Метод": _movie()})
    storage_data.save_meta({"Метод": {"raw_scores": {"tmdb_id": 693}}})

    assert "Метод" in storage_data.load_dataset()
    assert storage_data.load_meta()["Метод"]["raw_scores"]["tmdb_id"] == 693

    storage_data.clean_dataset()
    assert storage_data.load_dataset() == {}
    assert "Метод" in storage_data.load_meta()

    storage_data.clean_meta()
    assert storage_data.load_meta() == {}


def test_sqlite_dataset_save_does_not_export_legacy_json(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)

    storage_data.save_dataset({"Alpha": _movie("Alpha")})

    assert storage_data.load_dataset()["Alpha"]["main_info"]["title"] == "Alpha"
    assert (tmp_path / "data" / "watched" / "titles.json").exists() is False


def test_sqlite_backend_rename_updates_dataset_and_meta(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    storage_data.save_dataset({"Old": _movie("Old")})
    storage_data.save_meta({"Old": {"main_info": _movie("Old")["main_info"], "raw_scores": {}}})

    assert storage_data.rename_movie_title("old", "New") is True

    assert list(storage_data.load_dataset()) == ["New"]
    assert list(storage_data.load_meta()) == ["New"]
    assert storage_data.load_dataset()["New"]["main_info"]["title"] == "New"
    assert storage_data.load_meta()["New"]["main_info"]["title"] == "New"


def test_sqlite_backend_add_update_delete_watched_record(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    from dataset.records import add as add_module
    from dataset.records.add import add_dataset_record
    from dataset.records.delete import delete_watched_record
    from dataset.records import delete as delete_module
    from dataset.records.update import update_dataset_record

    monkeypatch.setattr(add_module, "run_after_add_side_effects", lambda **_kwargs: [])
    monkeypatch.setattr(delete_module, "backup_before_watched_delete", lambda timestamp=None: [])
    monkeypatch.setattr(delete_module, "load_poster_cache", lambda: {})
    monkeypatch.setattr(delete_module, "save_poster_cache", lambda _cache: None)

    add_result = add_dataset_record(_movie("Alpha"))
    assert add_result.ok is True
    assert "Alpha" in storage_data.load_dataset()
    assert "Alpha" in storage_data.load_meta()

    update_result = update_dataset_record("Alpha", {"main_info": {"user_score": 9.0}})
    assert update_result.ok is True
    assert storage_data.load_dataset()["Alpha"]["main_info"]["user_score"] == 9.0

    delete_result = delete_watched_record("Alpha", timestamp="sqlite-test")
    assert delete_result.ok is True
    assert storage_data.load_dataset() == {}
    assert storage_data.load_meta() == {}
