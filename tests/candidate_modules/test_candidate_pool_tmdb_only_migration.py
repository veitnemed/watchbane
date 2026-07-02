"""Tests for the one-time TMDb-only candidate pool migration script."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import migrate_candidate_pool_tmdb_only as migration


def _write_pool(path, pool: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pool, ensure_ascii=False, indent=4), encoding="utf-8")


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _legacy_pool() -> dict:
    return {
        "old": {
            "title": "Old",
            "year": "2020",
            "tmdb_id": 11,
            "tmdb_score": 7.1,
            "tmdb_votes": 100,
            "tmdb_popularity": 12.5,
            "genres_tmdb": ["Drama"],
            "origin_country": ["US"],
            "imdb_id": "tt11",
            "source": "legacy",
            "kp_score": 8.0,
            "kp_votes": 1000,
            "kp_rating": 8.1,
            "kp_id": 123,
            "kp_status": "done",
            "kp_year": 2019,
            "imdb_score": 7.6,
            "imdb_rating": 7.7,
            "imdb_votes": 2000,
            "imdb_start_year": 2018,
            "imdb_end_year": 2021,
            "imdb_genres": ["Drama"],
            "imdb_title_type": "tvSeries",
            "imdb_is_adult": 0,
            "imdb_found_in_sql": True,
        },
        "missing_tmdb": {
            "title": "Needs Match",
            "first_air_date": "2021-03-04",
            "tmdb_score": 6.4,
            "tmdb_votes": 12,
            "genres": ["Comedy"],
            "countries": ["US"],
            "imdb_score": 7.0,
            "imdb_id": "tt22",
        },
    }


def test_dry_run_writes_report_without_changing_pool(monkeypatch, tmp_path) -> None:
    pool_path = tmp_path / "pool.json"
    report_path = tmp_path / "candidate_pool_tmdb_only_migration_report.json"
    original_pool = _legacy_pool()
    _write_pool(pool_path, original_pool)
    monkeypatch.setattr(migration.pool_repository.constant, "CANDIDATE_POOL_JSON", str(pool_path))

    report = migration.run_migration(apply=False, report_path=report_path)

    assert _read_json(pool_path) == original_pool
    assert report["mode"] == "dry-run"
    assert report["backup_path"] is None
    assert report["total_candidates"] == 2
    assert report["migrated_candidates"] == 2
    assert report["stripped_kp_imdb_fields_count"] == 16
    assert _read_json(report_path)["mode"] == "dry-run"
    assert not list(tmp_path.glob("pool.before_tmdb_only.*.json"))


def test_apply_creates_backup_and_migrates_pool(monkeypatch, tmp_path) -> None:
    pool_path = tmp_path / "pool.json"
    report_path = tmp_path / "candidate_pool_tmdb_only_migration_report.json"
    original_pool = _legacy_pool()
    _write_pool(pool_path, original_pool)
    monkeypatch.setattr(migration.pool_repository.constant, "CANDIDATE_POOL_JSON", str(pool_path))

    report = migration.run_migration(apply=True, report_path=report_path)

    saved = _read_json(pool_path)
    assert set(saved) == {"old", "missing_tmdb"}
    assert _read_json(report_path)["backup_path"] == report["backup_path"]
    assert report["candidates_with_tmdb_id"] == 1
    assert report["candidates_without_tmdb_id"] == 1
    assert report["complete_after_migration"] == 1
    assert report["incomplete_after_migration"] == 1

    backup_path = Path(report["backup_path"])
    assert backup_path.exists()
    assert _read_json(backup_path) == original_pool

    old = saved["old"]
    for field_name in migration.EXTERNAL_RATING_FIELDS:
        assert field_name not in old
        assert field_name not in saved["missing_tmdb"]
    assert old["source"] == "tmdb"
    assert old["source_provider"] == "tmdb"
    assert old["source_version"] == 2
    assert old["year"] == 2020
    assert old["imdb_id"] == "tt11"
    assert old["tmdb_id"] == 11
    assert old["tmdb_score"] == 7.1
    assert old["tmdb_votes"] == 100
    assert old["tmdb_popularity"] == 12.5
    assert old["is_complete"] is True
    assert old["missing_fields"] == []

    missing = saved["missing_tmdb"]
    assert missing["needs_tmdb_match"] is True
    assert missing["year"] == 2021
    assert missing["imdb_id"] == "tt22"
    assert "tmdb_id" not in missing or missing["tmdb_id"] is None
