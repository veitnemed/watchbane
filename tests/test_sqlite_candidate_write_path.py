from __future__ import annotations

from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.repositories import criteria_repository, pool_repository
from storage import data as storage_data


def _use_sqlite(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))


def _candidate(title: str, year: int, score: float = 8.0) -> dict:
    return {
        "title": title,
        "year": year,
        "media_type": "tv",
        "tmdb_score": score,
        "tmdb_votes": 1000,
        "tmdb_popularity": 20,
        "quality_score": score,
        "final_score": score,
        "genres": ["драма"],
        "genre_keys": ["drama"],
        "countries": ["US"],
        "country_codes": ["US"],
    }


def _watched_movie(title: str, year: int) -> dict:
    return {
        "main_info": {
            "title": title,
            "year": year,
            "user_score": 8,
            "country": "US",
            "media_type": "tv",
        },
        "raw_scores": {},
        "tags_vibe": {},
        "genre": {},
    }


def test_sqlite_backend_candidate_pool_save_dedupes_and_loads(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)

    pool_repository.save_candidate_pool(
        {
            "low": _candidate("Dark", 2017, 7.0),
            "high": _candidate("Dark", 2017, 9.0),
        }
    )

    loaded = pool_repository.load_candidate_pool()
    assert list(loaded) == ["dark|2017"]
    assert loaded["dark|2017"]["final_score"] == 9.0


def test_sqlite_backend_candidate_pool_save_purges_watched(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    storage_data.save_dataset({"Dark": _watched_movie("Dark", 2017)})

    pool_repository.save_candidate_pool(
        {
            "dark": _candidate("Dark", 2017, 9.0),
            "severance": _candidate("Severance", 2022, 8.0),
        }
    )

    assert list(pool_repository.load_candidate_pool()) == ["severance|2022"]


def test_sqlite_backend_criteria_save_patch_and_clear_pool(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    pool_repository.save_candidate_pool({"dark": _candidate("Dark", 2017)})
    criteria_repository.save_candidate_criteria(
        {COMMON_POOL_CRITERIA_NAME: {"count": 50, "genres": [], "excluded_genres": []}}
    )

    updated = criteria_repository.patch_criteria_filters(
        COMMON_POOL_CRITERIA_NAME,
        criteria_repository.load_candidate_criteria()[COMMON_POOL_CRITERIA_NAME],
        min_tmdb_score=8.5,
        genres=["drama"],
        excluded_genres=["comedy"],
    )
    clear_result = criteria_repository.clear_common_pool()

    assert updated["min_tmdb_score"] == 8.5
    assert criteria_repository.load_candidate_criteria()[COMMON_POOL_CRITERIA_NAME]["genres"] == ["drama"]
    assert clear_result == {"ok": True, "cleared": 1}
    assert pool_repository.load_candidate_pool() == {}


def test_sqlite_backend_delete_criteria_and_candidates(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    criteria_repository.save_candidate_criteria({"custom": {"count": 10}})
    pool_repository.save_candidate_pool(
        {
            "a": {**_candidate("A", 2020), "criteria_name": "custom"},
            "b": {**_candidate("B", 2021), "criteria_name": "pool"},
        }
    )

    result = criteria_repository.delete_criteria_and_candidates("custom")

    assert result == {"deleted_criteria": True, "deleted_candidates": 0}
    assert "custom" not in criteria_repository.load_candidate_criteria()
    assert set(pool_repository.load_candidate_pool()) == {"a|2020", "b|2021"}
