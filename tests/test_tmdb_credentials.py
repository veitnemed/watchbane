from __future__ import annotations

from apis import tmdb_api


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
