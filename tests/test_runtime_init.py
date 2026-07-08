from config import constant
from storage import profiles
from storage import runtime


def test_ensure_runtime_data_layout_initializes_sqlite_without_runtime_json(monkeypatch, tmp_path) -> None:
    watched_dir = tmp_path / "watched"
    candidates_dir = tmp_path / "candidates"
    cache_dir = tmp_path / "cache"
    exports_dir = tmp_path / "exports"
    logs_dir = tmp_path / "logs"
    backups_dir = tmp_path / "backups"

    titles_json = watched_dir / "titles.json"
    meta_json = watched_dir / "meta.json"
    pool_json = candidates_dir / "pool.json"
    criteria_json = candidates_dir / "criteria.json"
    watchlist_json = candidates_dir / "watchlist.json"
    hidden_json = candidates_dir / "hidden.json"

    monkeypatch.setattr(constant, "APP_DATA_DIR", str(tmp_path))
    profiles.set_base_data_dir(tmp_path)
    monkeypatch.setattr(constant, "WATCHED_DIR", str(watched_dir))
    monkeypatch.setattr(constant, "CANDIDATES_DIR", str(candidates_dir))
    monkeypatch.setattr(constant, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(constant, "EXPORTS_DIR", str(exports_dir))
    monkeypatch.setattr(constant, "LOGS_DIR", str(logs_dir))
    monkeypatch.setattr(constant, "BACKUP_DIR", str(backups_dir))
    monkeypatch.setattr(constant, "DATA_DIR", str(watched_dir))
    monkeypatch.setattr(constant, "DIR_META", str(watched_dir))
    monkeypatch.setattr(constant, "FILE_NAME", str(titles_json))
    monkeypatch.setattr(constant, "META_JSON", str(meta_json))
    monkeypatch.setattr(constant, "CANDIDATE_POOL_JSON", str(pool_json))
    monkeypatch.setattr(constant, "CRITERIA_POOL_JSON", str(criteria_json))
    monkeypatch.setattr(
        runtime,
        "RUNTIME_DIRECTORIES",
        (
            str(tmp_path),
            str(watched_dir),
            str(candidates_dir),
            str(cache_dir),
            str(exports_dir),
            str(logs_dir),
            str(backups_dir),
        ),
    )

    result = runtime.ensure_runtime_data_layout()

    assert result["ok"] is True
    assert result["backup_created"] is False
    assert result["backend"] == "sqlite"
    assert result["sqlite_schema_version"] == 2
    assert (tmp_path / "watchbane.sqlite3").is_file()
    for path in (titles_json, meta_json, pool_json, criteria_json, watchlist_json, hidden_json):
        assert path.exists() is False
