"""Tests for refreshing candidate_pool.json from TMDb."""

import json
from pathlib import Path

from candidates.repositories import pool_repository
from scripts import refresh_candidate_pool_from_tmdb as refresh


def _details(tmdb_id: int, title: str = "Show", year: int = 2020) -> dict:
    return {
        "id": tmdb_id,
        "name": title,
        "original_name": title,
        "first_air_date": f"{year}-01-01",
        "last_air_date": f"{year}-12-31",
        "overview": "Fresh overview",
        "genres": [{"id": 18, "name": "Drama"}],
        "origin_country": ["RU"],
        "production_countries": [{"iso_3166_1": "RU", "name": "Russia"}],
        "original_language": "ru",
        "vote_average": 8.0,
        "vote_count": 120,
        "popularity": 10.0,
        "external_ids": {"imdb_id": f"tt{tmdb_id}"},
        "aggregate_credits": {},
        "keywords": {"results": []},
    }


def _movie_details(tmdb_id: int, title: str = "Movie", year: int = 2009) -> dict:
    return {
        "id": tmdb_id,
        "title": title,
        "original_title": title,
        "release_date": f"{year}-03-06",
        "status": "Released",
        "runtime": 162,
        "overview": "Fresh movie overview",
        "genres": [{"id": 18, "name": "Drama"}],
        "production_countries": [{"iso_3166_1": "US", "name": "United States of America"}],
        "original_language": "en",
        "vote_average": 7.3,
        "vote_count": 9000,
        "popularity": 30.0,
        "external_ids": {"imdb_id": f"tt{tmdb_id}"},
        "credits": {},
        "keywords": {"keywords": []},
    }


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_refresh_by_tmdb_id_preserves_local_fields_and_strips_ratings(monkeypatch) -> None:
    calls = []

    def fake_details(tmdb_id, **_kwargs):
        calls.append(tmdb_id)
        return _details(tmdb_id)

    monkeypatch.setattr(refresh.tmdb_api, "get_tv_details", fake_details)
    candidate = {
        "title": "Old",
        "year": 2019,
        "tmdb_id": 101,
        "hidden": True,
        "user_notes": "keep",
        "criteria_name": "pool",
        "kp_score": 9.0,
        "imdb_score": 8.0,
    }

    updated, status = refresh.refresh_candidate(candidate, token="token")

    assert status == "refreshed_by_tmdb_id"
    assert calls == [101]
    assert updated["title"] == "Show"
    assert updated["hidden"] is True
    assert updated["user_notes"] == "keep"
    assert updated["criteria_name"] == "pool"
    assert updated["imdb_id"] == "tt101"
    assert updated["is_complete"] is True
    assert updated["quality_score"] > 0
    assert "kp_score" not in updated
    assert "imdb_score" not in updated


def test_refresh_missing_tmdb_id_matches_by_search(monkeypatch) -> None:
    monkeypatch.setattr(
        refresh.tmdb_api,
        "search_tv_by_name",
        lambda title, token=None: [
            {"id": 202, "name": title, "original_name": title, "first_air_date": "2020-01-01"},
        ],
    )
    monkeypatch.setattr(refresh.tmdb_api, "get_tv_details", lambda tmdb_id, **_kwargs: _details(tmdb_id, "Search", 2020))

    updated, status = refresh.refresh_candidate({"title": "Search", "year": 2020}, token="token")

    assert status == "matched_by_search"
    assert updated["tmdb_id"] == 202
    assert updated["title"] == "Search"


def test_refresh_movie_by_tmdb_id_uses_movie_details(monkeypatch) -> None:
    calls = []

    def fake_movie_details(tmdb_id, **_kwargs):
        calls.append(tmdb_id)
        return _movie_details(tmdb_id)

    monkeypatch.setattr(refresh.tmdb_api, "get_movie_details", fake_movie_details)
    monkeypatch.setattr(
        refresh.tmdb_api,
        "get_tv_details",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("tv details should not be called")),
    )

    updated, status = refresh.refresh_candidate(
        {"title": "Movie", "year": 2009, "media_type": "movie", "tmdb_id": 202},
        token="token",
    )

    assert status == "refreshed_by_tmdb_id"
    assert calls == [202]
    assert updated["media_type"] == "movie"
    assert updated["release_date"] == "2009-03-06"
    assert updated["runtime"] == 162


def test_refresh_movie_missing_tmdb_id_uses_movie_search(monkeypatch) -> None:
    search_calls = []

    def fake_search(title, token=None):
        search_calls.append(title)
        return [{"id": 202, "title": title, "release_date": "2009-03-06"}]

    monkeypatch.setattr(refresh.tmdb_api, "search_movie_by_title", fake_search)
    monkeypatch.setattr(refresh.tmdb_api, "get_movie_details", lambda tmdb_id, **_kwargs: _movie_details(tmdb_id, "Movie", 2009))

    updated, status = refresh.refresh_candidate(
        {"title": "Movie", "year": 2009, "media_type": "movie"},
        token="token",
    )

    assert status == "matched_by_search"
    assert search_calls == ["Movie"]
    assert updated["tmdb_id"] == 202
    assert updated["media_type"] == "movie"


def test_refresh_missing_tmdb_id_needs_manual_match_on_ambiguous_search(monkeypatch) -> None:
    monkeypatch.setattr(
        refresh.tmdb_api,
        "search_tv_by_name",
        lambda title, token=None: [
            {"id": 1, "name": title, "first_air_date": "2020-01-01"},
            {"id": 2, "name": title, "first_air_date": "2020-02-01"},
        ],
    )
    monkeypatch.setattr(
        refresh.tmdb_api,
        "get_tv_details",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("details should not be called")),
    )

    updated, status = refresh.refresh_candidate({"title": "Show", "year": 2020}, token="token")

    assert status == "needs_manual_match"
    assert updated["title"] == "Show"


def test_refresh_pool_apply_creates_backup_and_report(monkeypatch, tmp_path) -> None:
    report_path = tmp_path / "report.json"
    original_pool = {
        "show|2020": {
            "title": "Show",
            "year": 2020,
            "tmdb_id": 101,
            "kp_votes": 100,
        },
        "missing|2021": {
            "title": "Missing",
            "year": 2021,
        },
    }
    pool_repository.save_candidate_pool(original_pool)
    canonical_original_pool = pool_repository.load_candidate_pool()
    monkeypatch.setattr(refresh.tmdb_api, "load_tmdb_token", lambda: "token")
    monkeypatch.setattr(refresh.tmdb_api, "get_tv_details", lambda tmdb_id, **_kwargs: _details(tmdb_id, year=2020))
    monkeypatch.setattr(refresh.tmdb_api, "search_tv_by_name", lambda *_args, **_kwargs: [])

    report = refresh.run_refresh(apply=True, report_path=report_path)

    saved = pool_repository.load_candidate_pool()
    assert report["backup_path"] is not None
    assert Path(report["backup_path"]).exists()
    assert _read_json(Path(report["backup_path"])) == canonical_original_pool
    assert _read_json(report_path)["refreshed_by_tmdb_id"] == 1
    assert report["failed"] == 1
    assert report["complete_after_refresh"] == 1
    assert report["incomplete_after_refresh"] == 1
    assert "kp_votes" not in saved["show|2020"]
    assert saved["missing|2021"]["title"] == "Missing"


def test_only_missing_skips_candidates_with_tmdb_id(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(refresh.tmdb_api, "get_tv_details", lambda *_args, **_kwargs: calls.append("details"))
    monkeypatch.setattr(refresh.tmdb_api, "search_tv_by_name", lambda *_args, **_kwargs: [])
    pool = {
        "with|2020": {"title": "With", "year": 2020, "tmdb_id": 1},
        "without|2021": {"title": "Without", "year": 2021},
    }

    _pool, stats = refresh.refresh_pool(pool, only_missing=True, token="token")

    assert calls == []
    assert stats["processed"] == 1
    assert stats["failed"] == 1
