"""Tests for pool repository read/write boundary."""

import json
import uuid
from pathlib import Path

import pytest

from candidates.repositories import pool_repository


def _workspace_tmp_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "cache" / f"pytest-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_load_candidate_pool_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_dir = _workspace_tmp_dir()
    pool_path = tmp_dir / "candidate_pool.json"
    pool_path.write_text(json.dumps({"k": {"title": "A", "year": 2020}}), encoding="utf-8")
    monkeypatch.setattr(pool_repository.constant, "CANDIDATE_POOL_JSON", str(pool_path))

    before_mtime = pool_path.stat().st_mtime
    loaded = pool_repository.load_candidate_pool()
    after_mtime = pool_path.stat().st_mtime

    assert loaded == {"k": {"title": "A", "year": 2020}}
    assert after_mtime == before_mtime


def test_save_candidate_pool_normalizes_and_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_dir = _workspace_tmp_dir()
    pool_path = tmp_dir / "candidate_pool.json"
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
