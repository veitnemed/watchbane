from __future__ import annotations

from candidates import service
from candidates.repositories import criteria_repository, pool_repository
from storage.sqlite import candidate_repository


def _use_sqlite(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.constant.APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})


def _candidate(title: str, year: int, score: float) -> dict:
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


def test_sqlite_runtime_routes_candidate_repository_reads(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    candidate_repository.save_candidate_pool_dict(
        {"dark": _candidate("Dark", 2017, 9.0)},
        purge_watched=False,
    )
    candidate_repository.save_candidate_criteria_dict({"pool": {"min_tmdb_score": 8.0}})

    assert pool_repository.load_candidate_pool()["dark|2017"]["title"] == "Dark"
    assert criteria_repository.load_candidate_criteria() == {"pool": {"min_tmdb_score": 8.0}}


def test_sqlite_runtime_candidate_service_views_use_pool_and_criteria(tmp_path, monkeypatch) -> None:
    _use_sqlite(tmp_path, monkeypatch)
    candidate_repository.save_candidate_pool_dict(
        {
            "dark-low": _candidate("Dark", 2017, 8.0),
            "severance": _candidate("Severance", 2022, 9.0),
        },
        purge_watched=False,
    )
    candidate_repository.save_candidate_criteria_dict(
        {"pool": {"min_tmdb_score": 8.5, "genres": ["drama"]}}
    )

    pool_view = service.get_pool_view()
    stats = service.get_pool_stats_view()["stats"]
    defaults = service.get_search_filter_defaults_view()
    filtered = service.get_search_filter_view(pool_view, {"min_tmdb_score": 8.5})
    duplicate_view = service.get_title_duplicates_view()

    assert {candidate["title"] for candidate in pool_view} == {"Dark", "Severance"}
    assert stats["storage_total"] == 2
    assert defaults["has_defaults"] is True
    assert [candidate["title"] for candidate in filtered["candidates"]] == ["Severance"]
    assert duplicate_view["group_count"] == 0


def test_pool_stats_cache_reuses_same_revision_and_invalidates_after_write(tmp_path, monkeypatch) -> None:
    from candidates.pool import stats as pool_stats

    _use_sqlite(tmp_path, monkeypatch)
    candidate_repository.save_candidate_pool_dict(
        {"first": _candidate("First", 2020, 8.0)},
        purge_watched=False,
    )
    pool_stats.clear_pool_stats_cache()
    original = pool_stats.dedupe_pool_by_similar_titles
    calls = 0

    def counted(pool):
        nonlocal calls
        calls += 1
        return original(pool)

    monkeypatch.setattr(pool_stats, "dedupe_pool_by_similar_titles", counted)

    assert service.get_pool_stats_view()["stats"]["storage_total"] == 1
    assert service.get_pool_stats_view()["stats"]["storage_total"] == 1
    assert calls == 0  # Duplicate analysis is skipped for a one-row pool.

    candidate_repository.save_candidate_pool_dict(
        {
            "first": _candidate("First", 2020, 8.0),
            "second": _candidate("Second", 2021, 7.0),
        },
        purge_watched=False,
    )
    assert service.get_pool_stats_view()["stats"]["storage_total"] == 2
    assert service.get_pool_stats_view()["stats"]["storage_total"] == 2
    assert calls == 1
