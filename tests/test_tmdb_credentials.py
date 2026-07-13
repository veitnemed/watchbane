from __future__ import annotations

import os

import pytest

from apis import tmdb_api


@pytest.fixture(autouse=True)
def _isolate_tmdb_environment(monkeypatch):
    for key in (
        "TMDB_ACCESS_TOKEN",
        "TMDB_TOKEN",
        "TMDB_API_KEY",
        "WATCHBANE_TMDB_CREDENTIALS_DISABLED",
    ):
        monkeypatch.delenv(key, raising=False)


def test_save_tmdb_bearer_token_writes_app_data_env_local(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))

    tmdb_api.save_tmdb_bearer_token("secret-token")

    env_path = tmp_path / "data" / ".env.local"
    assert env_path.is_file()
    payload = env_path.read_text(encoding="utf-8")
    assert "TMDB_ACCESS_TOKEN=secret-token" in payload
    assert "secret-token" not in payload.replace("TMDB_ACCESS_TOKEN=secret-token", "")


def test_save_tmdb_bearer_token_merges_existing_keys(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    data_dir.mkdir(parents=True)
    env_path = data_dir / ".env.local"
    env_path.write_text("CUSTOM_FLAG=1\nTMDB_ACCESS_TOKEN=old\n", encoding="utf-8")

    tmdb_api.save_tmdb_bearer_token("new-token")

    payload = env_path.read_text(encoding="utf-8")
    assert "CUSTOM_FLAG=1" in payload
    assert "TMDB_ACCESS_TOKEN=new-token" in payload
    assert "old" not in payload


def test_has_tmdb_credentials_reads_app_data_env_local(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(tmdb_api, "_load_all_tmdb_env_files", tmdb_api.load_app_data_dotenv)
    monkeypatch.delenv("TMDB_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TMDB_TOKEN", raising=False)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)

    assert tmdb_api.has_tmdb_credentials() is False

    tmdb_api.save_tmdb_bearer_token("secret-token")

    assert tmdb_api.has_tmdb_credentials() is True
    assert tmdb_api.load_tmdb_token() == "secret-token"


def test_bearer_prefix_and_outer_whitespace_are_normalized(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))

    tmdb_api.save_tmdb_bearer_token("  Bearer secret-token  \n")

    assert tmdb_api.get_tmdb_env_path().read_text(encoding="utf-8").endswith(
        "TMDB_ACCESS_TOKEN=secret-token\n"
    )
    assert tmdb_api.load_tmdb_credentials() == ("bearer", "secret-token")


@pytest.mark.parametrize("value", ["one\ntwo", "one\rtwo", "one two", "Bearer "])
def test_save_rejects_multiline_or_ambiguous_token_without_touching_existing(
    tmp_path, monkeypatch, value
) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    tmdb_api.save_tmdb_bearer_token("kept-token")
    before = tmdb_api.get_tmdb_env_path().read_bytes()

    with pytest.raises(ValueError):
        tmdb_api.save_tmdb_bearer_token(value)

    assert tmdb_api.get_tmdb_env_path().read_bytes() == before
    assert tmdb_api.load_tmdb_token() == "kept-token"


def test_delete_credentials_preserves_unrelated_env_and_clears_legacy_formats(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    env_path = data_dir / ".env.local"
    env_path.write_text(
        "CUSTOM_FLAG=1\nTMDB_TOKEN=legacy-token\nTMDB_API_KEY=legacy-key\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TMDB_ACCESS_TOKEN", "runtime-token")
    monkeypatch.setenv("TMDB_TOKEN", "legacy-token")
    monkeypatch.setenv("TMDB_API_KEY", "legacy-key")

    assert tmdb_api.delete_tmdb_credentials() is True

    assert env_path.read_text(encoding="utf-8") == (
        "CUSTOM_FLAG=1\nWATCHBANE_TMDB_CREDENTIALS_DISABLED=1\n"
    )
    assert all(
        key not in os.environ
        for key in ("TMDB_ACCESS_TOKEN", "TMDB_TOKEN", "TMDB_API_KEY")
    )
    assert tmdb_api.has_tmdb_credentials() is False


def test_legacy_api_key_is_still_loaded(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    (data_dir / "tmdb.env").write_text("TMDB_API_KEY=legacy-key\n", encoding="utf-8")
    for key in ("TMDB_ACCESS_TOKEN", "TMDB_TOKEN", "TMDB_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(tmdb_api, "_load_all_tmdb_env_files", tmdb_api.load_app_data_dotenv)

    assert tmdb_api.load_tmdb_credentials() == ("api_key", "legacy-key")


def test_replace_and_delete_credentials_do_not_touch_local_user_data(tmp_path, monkeypatch) -> None:
    from storage.sqlite import recommendation_deck_repository, watched_repository

    data_dir = tmp_path / "data"
    db_path = data_dir / "watchbane.sqlite3"
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    watched = {
        "Local": {
            "main_info": {"title": "Local", "year": 2024, "media_type": "movie"}
        }
    }
    deck = {"deck_id": "local-deck", "active": [{"title": "Candidate"}], "reserve": []}
    watched_repository.save_dataset_dict(watched, path=db_path)
    recommendation_deck_repository.save_current_deck(deck, path=db_path)

    tmdb_api.save_tmdb_bearer_token("first-token")
    tmdb_api.save_tmdb_bearer_token("replacement-token")
    tmdb_api.delete_tmdb_credentials()

    assert watched_repository.load_dataset_dict(path=db_path) == watched
    assert recommendation_deck_repository.load_current_deck(path=db_path) == deck
