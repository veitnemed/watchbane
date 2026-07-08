"""Tests for candidates.service read-path contract."""

import pytest

from candidates import service as candidate_service
from candidates.repositories import pool_repository


def test_get_pool_view_uses_sqlite_read_path() -> None:
    view = candidate_service.get_pool_view()

    assert isinstance(view, list)


def test_get_pool_stats_view_uses_sqlite_read_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "candidates.pool.watched_cleanup.build_watched_signatures",
        lambda: set(),
    )
    monkeypatch.setattr(
        "candidates.pool.watched_cleanup.build_dataset_title_keys",
        lambda: set(),
    )

    stats_view = candidate_service.get_pool_stats_view()

    assert "stats" in stats_view


def test_service_clean_common_pool_duplicates_delegates_without_recursion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_clean_common_pool_duplicates(*, merge_similar=True, merge_cross_year=True):
        calls.append((merge_similar, merge_cross_year))
        return {"ok": True, "removed_total": 0}

    monkeypatch.setattr(
        candidate_service,
        "_clean_common_pool_duplicates_impl",
        fake_clean_common_pool_duplicates,
    )

    result = candidate_service.clean_common_pool_duplicates(
        merge_similar=False,
        merge_cross_year=True,
    )

    assert result == {"ok": True, "removed_total": 0}
    assert calls == [(False, True)]


def test_service_ensure_common_pool_criteria_delegates_without_recursion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        candidate_service,
        "_ensure_common_pool_criteria_impl",
        lambda: ("pool", {"country": "RU"}),
    )

    assert candidate_service.ensure_common_pool_criteria() == ("pool", {"country": "RU"})


def test_service_format_candidate_description_delegates_without_recursion() -> None:
    description = candidate_service.format_candidate_description(
        {"description": "A long description"},
        limit=6,
    )

    assert description == "A l..."


def test_metadata_diagnostics_reports_incomplete_sqlite_candidates() -> None:
    payload = {
        "incomplete": {"title": "Missing fields", "criteria_name": "pool"},
        "complete": {
            "title": "Complete",
            "year": 2020,
            "tmdb_id": 123,
            "tmdb_score": 7.5,
            "tmdb_votes": 200,
            "genres_tmdb": ["Drama"],
            "country_codes": ["US"],
            "criteria_name": "pool",
        },
    }
    pool_repository.save_candidate_pool(payload)

    view = candidate_service.get_metadata_diagnostics_view()

    assert view["is_empty"] is False
    assert view["incomplete_count"] == 1
    assert view["incomplete_candidates"][0]["title"] == "Missing fields"
    assert "missing_fields" in view["incomplete_candidates"][0]
