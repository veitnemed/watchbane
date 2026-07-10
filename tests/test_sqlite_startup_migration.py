from __future__ import annotations

import json
from pathlib import Path

from storage import profiles
from storage import runtime
from storage.sqlite import watched_repository
from storage.sqlite.settings_repository import get_setting


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _patch_runtime(tmp_path, monkeypatch) -> Path:
    data_dir = tmp_path / "data"
    watched_dir = data_dir / "watched"
    candidates_dir = data_dir / "candidates"
    cache_dir = data_dir / "cache"
    exports_dir = data_dir / "exports"
    logs_dir = data_dir / "logs"
    backup_dir = data_dir / "backups"
    profiles.set_base_data_dir(data_dir)
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    monkeypatch.setattr("config.constant.WATCHED_DIR", str(watched_dir))
    monkeypatch.setattr("config.constant.CANDIDATES_DIR", str(candidates_dir))
    monkeypatch.setattr("config.constant.CACHE_DIR", str(cache_dir))
    monkeypatch.setattr("config.constant.EXPORTS_DIR", str(exports_dir))
    monkeypatch.setattr("config.constant.LOGS_DIR", str(logs_dir))
    monkeypatch.setattr("config.constant.BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(runtime, "RUNTIME_DIRECTORIES", (
        str(data_dir),
        str(watched_dir),
        str(candidates_dir),
        str(cache_dir),
        str(exports_dir),
        str(logs_dir),
        str(backup_dir),
    ))
    return data_dir


def test_sqlite_startup_does_not_import_existing_legacy_json_automatically(tmp_path, monkeypatch) -> None:
    data_dir = _patch_runtime(tmp_path, monkeypatch)
    _write_json(
        data_dir / "watched" / "titles.json",
        {"Legacy": {"main_info": {"title": "Legacy", "year": 2015, "user_score": 8, "country": "US"}}},
    )
    _write_json(data_dir / "watched" / "meta.json", {"Legacy": {"raw_scores": {"tmdb_id": 693}}})

    result = runtime.ensure_runtime_data_layout()

    db_path = Path(result["sqlite_db_path"])
    assert result["sqlite_startup_migration"]["legacy_imported"] is False
    assert watched_repository.load_dataset_dict(path=db_path) == {}
    assert watched_repository.load_meta_dict(path=db_path) == {}
    assert get_setting("legacy_json_import_completed", path=db_path) is None


def test_sqlite_startup_without_legacy_data_creates_empty_db(tmp_path, monkeypatch) -> None:
    _patch_runtime(tmp_path, monkeypatch)

    result = runtime.ensure_runtime_data_layout()

    db_path = Path(result["sqlite_db_path"])
    assert db_path.is_file()
    assert result["sqlite_startup_migration"]["legacy_imported"] is False
    assert watched_repository.load_dataset_dict(path=db_path) == {}
    assert get_setting("legacy_json_import_completed", path=db_path) is None
