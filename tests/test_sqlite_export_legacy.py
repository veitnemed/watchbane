from __future__ import annotations

import json
from pathlib import Path

from candidates.pool.normalization import normalize_storage_pool
from storage.normalize import normalize_movie_tags
from storage.sqlite.export_legacy import export_sqlite_to_legacy_json
from storage.sqlite.import_legacy import import_legacy_json_to_sqlite


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_export_sqlite_to_legacy_json_preserves_file_names(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    output_dir = tmp_path / "export"
    from storage.sqlite import watched_repository

    watched_repository.save_dataset_dict(
        {"Метод": {"main_info": {"title": "Метод", "year": 2015, "user_score": 8, "country": "Россия"}}},
        path=db_path,
    )

    report = export_sqlite_to_legacy_json(output_dir=output_dir, db_path=db_path)

    assert report["counts"]["watched/titles.json"] == 1
    for relative_path in (
        "watched/titles.json",
        "watched/meta.json",
        "candidates/pool.json",
        "candidates/criteria.json",
        "candidates/watchlist.json",
        "candidates/hidden.json",
        "settings.json",
        "cache/posters/posters.json",
    ):
        assert (output_dir / relative_path).is_file()


def test_export_sqlite_to_legacy_json_writes_complete_json_files(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    output_dir = tmp_path / "export"
    from storage.sqlite import settings_repository

    settings_repository.save_settings_dict({"ui_scale": 1.25}, path=db_path)

    export_sqlite_to_legacy_json(output_dir=output_dir, db_path=db_path)

    settings_path = output_dir / "settings.json"
    assert settings_path.read_text(encoding="utf-8").endswith("\n")
    assert _read_json(settings_path) == {"ui_scale": 1.25}
    assert (output_dir / "settings.json.tmp").exists() is False


def test_import_then_export_matches_canonicalized_legacy_data(tmp_path) -> None:
    base = tmp_path / "data"
    db_path = tmp_path / "watchbane.sqlite3"
    output_dir = tmp_path / "export"
    watched = {
        "Метод": {
            "main_info": {
                "title": "Метод",
                "year": 2015,
                "user_score": 8,
                "country": "Россия",
            },
            "raw_scores": {},
            "tags_vibe": {},
            "genre": {},
        }
    }
    pool = {"legacy": {"title": "Dark", "year": 2017, "final_score": 9}}
    payloads = {
        base / "watched" / "titles.json": watched,
        base / "watched" / "meta.json": {"Метод": {"raw_scores": {"tmdb_id": 693}}},
        base / "candidates" / "pool.json": pool,
        base / "candidates" / "criteria.json": {"pool": {"count": 50}},
        base / "candidates" / "watchlist.json": {"dark|2017": {"candidate": {"title": "Dark", "year": 2017}, "added_at": "2026-01-01T00:00:00"}},
        base / "candidates" / "hidden.json": {},
        base / "settings.json": {"ui_scale": 1.25},
        base / "cache" / "posters" / "posters.json": {"метод|2015": {"title": "Метод", "year": 2015, "status": "found"}},
    }
    for path, payload in payloads.items():
        _write_json(path, payload)

    import_legacy_json_to_sqlite(base_dir=base, db_path=db_path, create_backup=False)
    export_sqlite_to_legacy_json(output_dir=output_dir, db_path=db_path)

    assert _read_json(output_dir / "watched" / "titles.json") == {
        key: normalize_movie_tags(value) for key, value in watched.items()
    }
    assert _read_json(output_dir / "watched" / "meta.json") == payloads[base / "watched" / "meta.json"]
    assert _read_json(output_dir / "candidates" / "pool.json") == normalize_storage_pool(pool)
    assert _read_json(output_dir / "candidates" / "criteria.json") == {"pool": {"count": 50}}
    assert _read_json(output_dir / "candidates" / "watchlist.json") == payloads[base / "candidates" / "watchlist.json"]
    assert _read_json(output_dir / "settings.json") == {"ui_scale": 1.25}
    assert _read_json(output_dir / "cache" / "posters" / "posters.json") == payloads[base / "cache" / "posters" / "posters.json"]
