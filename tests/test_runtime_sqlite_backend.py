from __future__ import annotations

from pathlib import Path

from storage import runtime


def test_runtime_initializes_sqlite_when_backend_is_sqlite(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    watched_dir = data_dir / "watched"
    candidates_dir = data_dir / "candidates"
    cache_dir = data_dir / "cache"
    exports_dir = data_dir / "exports"
    logs_dir = data_dir / "logs"
    backup_dir = data_dir / "backups"
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    monkeypatch.setattr("config.constant.WATCHED_DIR", str(watched_dir))
    monkeypatch.setattr("config.constant.CANDIDATES_DIR", str(candidates_dir))
    monkeypatch.setattr("config.constant.CACHE_DIR", str(cache_dir))
    monkeypatch.setattr("config.constant.EXPORTS_DIR", str(exports_dir))
    monkeypatch.setattr("config.constant.LOGS_DIR", str(logs_dir))
    monkeypatch.setattr("config.constant.BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr("config.constant.FILE_NAME", str(watched_dir / "titles.json"))
    monkeypatch.setattr("config.constant.META_JSON", str(watched_dir / "meta.json"))
    monkeypatch.setattr("config.constant.CANDIDATE_POOL_JSON", str(candidates_dir / "pool.json"))
    monkeypatch.setattr("config.constant.CRITERIA_POOL_JSON", str(candidates_dir / "criteria.json"))
    monkeypatch.setattr(runtime, "RUNTIME_DIRECTORIES", (
        str(data_dir),
        str(watched_dir),
        str(candidates_dir),
        str(cache_dir),
        str(exports_dir),
        str(logs_dir),
        str(backup_dir),
    ))

    result = runtime.ensure_runtime_data_layout()

    assert result["backend"] == "sqlite"
    assert result["sqlite_schema_version"] == 1
    assert Path(result["sqlite_db_path"]).is_file()
    assert (watched_dir / "titles.json").exists() is False
