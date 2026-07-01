"""Tests for candidates.service read-path contract."""

import uuid
from pathlib import Path

import pytest

from candidates import service as candidate_service


def _workspace_pool_path() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "cache" / f"pytest-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    pool_path = path / "candidate_pool.json"
    pool_path.write_text("{}", encoding="utf-8")
    return pool_path


def test_get_pool_view_does_not_write_json(monkeypatch: pytest.MonkeyPatch) -> None:
    pool_path = _workspace_pool_path()
    monkeypatch.setattr(
        "candidates.repositories.pool_repository.constant.CANDIDATE_POOL_JSON",
        str(pool_path),
    )

    before_mtime = pool_path.stat().st_mtime
    view = candidate_service.get_pool_view()
    after_mtime = pool_path.stat().st_mtime

    assert isinstance(view, list)
    assert after_mtime == before_mtime


def test_get_pool_stats_view_does_not_write_json(monkeypatch: pytest.MonkeyPatch) -> None:
    pool_path = _workspace_pool_path()
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
