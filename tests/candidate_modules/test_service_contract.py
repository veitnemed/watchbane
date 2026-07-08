"""Tests for candidates.service read-path contract."""

import json

import pytest

from candidates import service as candidate_service


def _pool_path(tmp_path):
    pool_path = tmp_path / "candidate_pool.json"
    pool_path.write_text("{}", encoding="utf-8")
    return pool_path


def test_get_pool_view_does_not_write_json(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    pool_path = _pool_path(tmp_path)
    monkeypatch.setattr(
        "candidates.repositories.pool_repository.constant.CANDIDATE_POOL_JSON",
        str(pool_path),
    )

    before_mtime = pool_path.stat().st_mtime
    view = candidate_service.get_pool_view()
    after_mtime = pool_path.stat().st_mtime

    assert isinstance(view, list)
    assert after_mtime == before_mtime


def test_get_pool_stats_view_does_not_write_json(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    pool_path = _pool_path(tmp_path)
    monkeypatch.setattr(
        "candidates.repositories.pool_repository.constant.CANDIDATE_POOL_JSON",
        str(pool_path),
    )
    monkeypatch.setattr(
        "candidates.pool.watched_cleanup.build_watched_signatures",
        lambda: set(),
    )
    monkeypatch.setattr(
        "candidates.pool.watched_cleanup.build_dataset_title_keys",
        lambda: set(),
    )

    before_mtime = pool_path.stat().st_mtime
    stats_view = candidate_service.get_pool_stats_view()
    after_mtime = pool_path.stat().st_mtime

    assert "stats" in stats_view
    assert after_mtime == before_mtime


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


def test_metadata_diagnostics_skips_non_object_pool_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    pool_path = tmp_path / "candidate_pool.json"
    payload = {
        "broken": "not a candidate",
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
    pool_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        "candidates.repositories.pool_repository.constant.CANDIDATE_POOL_JSON",
        str(pool_path),
    )

    before = pool_path.read_text(encoding="utf-8")
    view = candidate_service.get_metadata_diagnostics_view()

    assert view["is_empty"] is False
    assert view["incomplete_count"] == 1
    assert view["incomplete_candidates"] == [payload["incomplete"]]
    assert pool_path.read_text(encoding="utf-8") == before
