from __future__ import annotations

import json

from app.core import storage as action_storage
from candidates.repositories import pool_repository
from config import constant
from dataset.records.add import add_dataset_record
from dataset.records.delete import delete_watched_record
from dataset.records.update import update_dataset_record
from posters.cache import lookup_poster_cache_entry, upsert_poster_cache_entry
from storage import data as storage_data
from storage import runtime
from storage.legacy_json.importer import import_legacy_json_to_sqlite


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _patch_runtime(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    watched_dir = data_dir / "watched"
    candidates_dir = data_dir / "candidates"
    cache_dir = data_dir / "cache"
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(data_dir))
    monkeypatch.setattr("config.constant.WATCHED_DIR", str(watched_dir))
    monkeypatch.setattr("config.constant.CANDIDATES_DIR", str(candidates_dir))
    monkeypatch.setattr("config.constant.CACHE_DIR", str(cache_dir))
    monkeypatch.setattr("config.constant.EXPORTS_DIR", str(data_dir / "exports"))
    monkeypatch.setattr("config.constant.LOGS_DIR", str(data_dir / "logs"))
    monkeypatch.setattr("config.constant.BACKUP_DIR", str(data_dir / "backups"))
    monkeypatch.setattr(runtime, "RUNTIME_DIRECTORIES", (
        str(data_dir),
        str(watched_dir),
        str(candidates_dir),
        str(cache_dir),
        str(data_dir / "exports"),
        str(data_dir / "logs"),
        str(data_dir / "backups"),
    ))
    return data_dir


def _watched_payload(title: str, year: int) -> dict:
    return {
        "main_info": {
            "title": title,
            "year": year,
            "user_score": 8.0,
            "country": "US",
            "media_type": "tv",
        },
        "raw_scores": {
            "tmdb_score": 8.0,
            "tmdb_votes": 1000,
            "tmdb_popularity": 42.5,
        },
    }


def test_sqlite_end_to_end_runtime_smoke(tmp_path, monkeypatch) -> None:
    data_dir = _patch_runtime(tmp_path, monkeypatch)
    _write_json(data_dir / "watched" / "titles.json", {"Legacy": _watched_payload("Legacy", 2020)})

    startup = runtime.ensure_runtime_data_layout()
    assert startup["sqlite_startup_migration"]["legacy_imported"] is False
    import_legacy_json_to_sqlite(
        base_dir=data_dir,
        db_path=startup["sqlite_db_path"],
        create_backup=False,
    )
    assert "Legacy" in storage_data.load_dataset()

    add_result = add_dataset_record(_watched_payload("Alpha", 2021))
    assert add_result.ok is True
    update_result = update_dataset_record("Alpha", {"main_info": {"user_score": 9.0}})
    assert update_result.ok is True
    assert storage_data.load_dataset()["Alpha"]["main_info"]["user_score"] == 9.0

    pool_repository.save_candidate_pool(
        {"candidate": {"title": "Candidate", "year": 2022, "tmdb_score": 8.5, "final_score": 8.5}}
    )
    assert list(pool_repository.load_candidate_pool()) == ["candidate|2022"]

    assert action_storage.add_to_watchlist({"title": "Candidate", "year": 2022})["ok"] is True
    assert action_storage.add_to_hidden({"title": "Candidate", "year": 2022})["ok"] is True
    assert action_storage.load_watchlist_identities() == set()
    assert action_storage.load_hidden_identities() == {"candidate|2022|tv"}

    upsert_poster_cache_entry(
        "Candidate",
        2022,
        {"poster_path": "/c.jpg", "poster_url": "https://example.test/c.jpg", "status": "found"},
    )
    assert lookup_poster_cache_entry("Candidate", 2022)["poster_path"] == "/c.jpg"

    from dataset.records import delete as delete_module

    monkeypatch.setattr(delete_module, "backup_before_watched_delete", lambda timestamp=None: [])
    delete_result = delete_watched_record("Alpha", timestamp="sqlite-smoke")
    assert delete_result.ok is True
    assert "Alpha" not in storage_data.load_dataset()
