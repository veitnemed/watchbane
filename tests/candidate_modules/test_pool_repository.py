"""Tests for pool repository read/write boundary."""

import json

import pytest

from candidates.repositories import criteria_repository
from candidates.repositories import json_io
from candidates.repositories import pool_repository
from storage import files as storage_files


def _tmdb_candidate(**overrides) -> dict:
    candidate = {
        "title": "Show",
        "year": 2018,
        "tmdb_id": 123,
        "tmdb_score": 7.5,
        "tmdb_votes": 200,
        "genres_tmdb": ["Drama"],
        "country_codes": ["US"],
    }
    candidate.update(overrides)
    return candidate


def test_load_candidate_pool_read_only(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    pool_path = tmp_path / "candidate_pool.json"
    pool_path.write_text(json.dumps({"k": {"title": "A", "year": 2020}}), encoding="utf-8")
    monkeypatch.setattr(pool_repository.constant, "CANDIDATE_POOL_JSON", str(pool_path))

    before_mtime = pool_path.stat().st_mtime
    loaded = pool_repository.load_candidate_pool()
    after_mtime = pool_path.stat().st_mtime

    assert loaded == {"k": {"title": "A", "year": 2020}}
    assert after_mtime == before_mtime


def test_load_candidate_pool_missing_file_is_read_only(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    pool_path = tmp_path / "candidate_pool.json"
    monkeypatch.setattr(pool_repository.constant, "CANDIDATE_POOL_JSON", str(pool_path))

    assert pool_repository.load_candidate_pool() == {}
    assert not pool_path.exists()


def test_load_candidate_criteria_missing_file_is_read_only(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    criteria_path = tmp_path / "candidate_criteria.json"
    monkeypatch.setattr(criteria_repository.constant, "CRITERIA_POOL_JSON", str(criteria_path))

    assert criteria_repository.load_candidate_criteria() == {}
    assert not criteria_path.exists()


def test_save_candidate_criteria_creates_parent_dir(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    criteria_path = tmp_path / "nested" / "candidate_criteria.json"
    monkeypatch.setattr(criteria_repository.constant, "CRITERIA_POOL_JSON", str(criteria_path))

    criteria_repository.save_candidate_criteria({"pool": {"count": 10}})

    assert json.loads(criteria_path.read_text(encoding="utf-8")) == {"pool": {"count": 10}}


def test_atomic_candidate_json_write_preserves_existing_file_on_replace_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    target_path = tmp_path / "candidate_pool.json"
    original = {"existing": {"title": "Keep"}}
    target_path.write_text(json.dumps(original), encoding="utf-8")

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr(storage_files.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        json_io.dump_json_atomic(str(target_path), {"new": {"title": "Drop"}})

    assert json.loads(target_path.read_text(encoding="utf-8")) == original
    assert not target_path.with_name(f"{target_path.name}.tmp").exists()


def test_save_candidate_pool_normalizes_and_writes(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    pool_path = tmp_path / "candidate_pool.json"
    pool_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(pool_repository.constant, "CANDIDATE_POOL_JSON", str(pool_path))
    monkeypatch.setattr(
        "candidates.pool.watched_cleanup.build_watched_signatures",
        lambda: set(),
    )
    monkeypatch.setattr(
        "candidates.pool.watched_cleanup.build_dataset_title_keys",
        lambda: set(),
    )

    pool_repository.save_candidate_pool({
        "legacy|show|2018": {"title": "Show", "year": 2018, "kp_score": 7.0},
        "show|2018": {"title": "Show", "year": 2018, "kp_score": 8.5},
    })

    saved = json.loads(pool_path.read_text(encoding="utf-8"))
    assert len(saved) == 1


def test_save_candidate_pool_strips_external_rating_fields(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    pool_path = tmp_path / "candidate_pool.json"
    pool_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(pool_repository.constant, "CANDIDATE_POOL_JSON", str(pool_path))
    monkeypatch.setattr(
        "candidates.pool.watched_cleanup.build_watched_signatures",
        lambda: set(),
    )
    monkeypatch.setattr(
        "candidates.pool.watched_cleanup.build_dataset_title_keys",
        lambda: set(),
    )

    pool_repository.save_candidate_pool({
        "show|2018": _tmdb_candidate(
            kp_score=8.0,
            kp_votes=100,
            kp_rating=8.1,
            kp_id=123,
            kp_status="done",
            kp_year=2018,
            imdb_score=7.5,
            imdb_rating=7.6,
            imdb_votes=200,
            imdb_start_year=2018,
            imdb_end_year=2020,
            imdb_genres=["Drama"],
            imdb_title_type="tvSeries",
            imdb_is_adult=0,
            imdb_found_in_sql=True,
            imdb_id="tt123",
            tmdb_popularity=10.5,
        )
    })

    saved = json.loads(pool_path.read_text(encoding="utf-8"))
    candidate = next(iter(saved.values()))
    for field_name in (
        "kp_score",
        "kp_votes",
        "kp_rating",
        "kp_id",
        "kp_status",
        "kp_year",
        "imdb_score",
        "imdb_rating",
        "imdb_votes",
        "imdb_start_year",
        "imdb_end_year",
        "imdb_genres",
        "imdb_title_type",
        "imdb_is_adult",
        "imdb_found_in_sql",
    ):
        assert field_name not in candidate
    assert candidate["imdb_id"] == "tt123"
    assert candidate["tmdb_id"] == 123
    assert candidate["tmdb_score"] == 7.5
    assert candidate["tmdb_votes"] == 200
    assert candidate["tmdb_popularity"] == 10.5


def test_tmdb_import_update_existing_strips_external_rating_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    from candidates.repositories import criteria_repository
    from candidates.sources.tmdb import importer

    saved: dict = {}
    existing = _tmdb_candidate(kp_score=7.0, imdb_rating=6.5, imdb_id="tt123")
    incoming = _tmdb_candidate(
        tmdb_score=8.2,
        tmdb_votes=500,
        kp_score=9.0,
        kp_votes=1000,
        imdb_rating=8.0,
        imdb_votes=2000,
        imdb_id="tt123",
    )

    monkeypatch.setattr(importer, "load_candidate_pool", lambda: {"show|2018": existing})
    monkeypatch.setattr(importer, "save_candidate_pool", lambda pool: saved.update({"pool": pool}))
    monkeypatch.setattr(importer, "build_watched_signatures", lambda: set())
    monkeypatch.setattr(importer, "build_dataset_title_keys", lambda: set())
    monkeypatch.setattr(criteria_repository, "load_candidate_criteria", lambda: {})
    monkeypatch.setattr(importer, "load_candidate_criteria", lambda: {})
    monkeypatch.setattr(importer, "save_named_criteria", lambda name, criteria: (name, criteria))

    result = importer.import_tmdb_candidates_to_common_pool([incoming], criteria_name="pool")

    assert result["updated"] == 1
    candidate = next(iter(saved["pool"].values()))
    assert candidate["tmdb_score"] == 8.2
    assert candidate["tmdb_votes"] == 500
    assert candidate["imdb_id"] == "tt123"
    for field_name in (
        "kp_score",
        "kp_votes",
        "kp_rating",
        "kp_id",
        "kp_status",
        "kp_year",
        "imdb_score",
        "imdb_rating",
        "imdb_votes",
        "imdb_start_year",
        "imdb_end_year",
        "imdb_genres",
        "imdb_title_type",
        "imdb_is_adult",
        "imdb_found_in_sql",
    ):
        assert field_name not in candidate
