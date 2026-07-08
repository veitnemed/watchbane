from __future__ import annotations

from app.core import storage as search_storage
from candidates import service
from desktop.settings.app_settings import AppSettings, load_app_settings, save_app_settings
from posters import cache as poster_cache
from storage.sqlite import action_repository, poster_repository, settings_repository


def _use_sqlite(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))


def test_sqlite_backend_routes_hidden_and_watchlist_actions(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    candidate = {"title": "Метод", "year": 2015}

    watchlist = service.add_candidate_to_watchlist(candidate)
    hidden = service.hide_candidate(candidate)

    assert watchlist["identity"] == "метод|2015"
    assert hidden["identity"] == "метод|2015"
    assert search_storage.load_watchlist_identities() == {"метод|2015"}
    assert search_storage.load_hidden_identities() == {"метод|2015"}
    assert action_repository.load_action_identities(action_repository.ACTION_HIDDEN) == {"метод|2015"}


def test_sqlite_backend_routes_app_settings(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)

    save_app_settings(AppSettings(ui_scale=1.25, interface_language="en", data_language="ru"))

    assert load_app_settings() == AppSettings(ui_scale=1.25, interface_language="en", data_language="ru")
    assert settings_repository.load_settings_dict()["ui_scale"] == 1.25


def test_sqlite_backend_routes_poster_cache_metadata(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)

    entry = poster_cache.upsert_poster_cache_entry(
        "Dark",
        2017,
        {
            "poster_path": "/dark.jpg",
            "poster_url": "https://example.test/dark.jpg",
            "local_path": "data/cache/posters/images/dark.jpg",
            "status": "found",
            "source": "test",
        },
    )

    assert entry["status"] == "found"
    assert (tmp_path / "data" / "watchbane.sqlite3").is_file()
    loaded_cache = poster_cache.load_poster_cache()
    assert loaded_cache
    assert poster_cache.lookup_poster_cache_entry("Dark", 2017)["poster_path"] == "/dark.jpg"
    assert poster_repository.lookup_poster_cache_entry("Dark", 2017)["local_path"].endswith("dark.jpg")
