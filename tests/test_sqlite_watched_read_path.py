from __future__ import annotations

from storage import data as storage_data
from storage.sqlite import watched_repository


def test_sqlite_runtime_routes_watched_read_path(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    watched_repository.save_dataset_dict(
        {
            "Метод": {
                "main_info": {
                    "title": "Метод",
                    "year": 2015,
                    "user_score": 8,
                    "country": "Россия",
                    "media_type": "tv",
                },
                "raw_scores": {},
                "tags_vibe": {},
                "genre": {},
            }
        }
    )

    assert storage_data.load_dataset()["Метод"]["main_info"]["title"] == "Метод"
    assert storage_data.get_all_titles() == ["Метод"]
    assert storage_data.find_exact_title(" метод ") == "Метод"
    assert storage_data.is_origin_title("Метод") is False


def test_sqlite_runtime_routes_watched_meta_read_path(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    watched_repository.save_meta_dict({"Метод": {"raw_scores": {"tmdb_id": 693}}})

    assert storage_data.load_meta() == {"Метод": {"raw_scores": {"tmdb_id": 693}}}
    assert storage_data.title_in_meta(" метод ") is True
    assert storage_data.get_meta_obj("МЕТОД") == {"raw_scores": {"tmdb_id": 693}}
