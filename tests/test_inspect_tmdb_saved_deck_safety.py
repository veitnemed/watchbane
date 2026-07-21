from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from storage.sqlite.candidate_pool_repository import save_candidate_pool_dict
from storage.sqlite.recommendation_deck_repository import save_current_deck
from tools.research.inspect_tmdb_saved_deck_safety import inspect_database


def _candidate(*, blocked: bool) -> dict:
    return {
        "media_type": "movie", "tmdb_id": 123 if blocked else 124, "title": "Private title",
        "year": 2020, "overview": "Private overview", "genres": ["Drama"], "country_codes": ["US"],
        "tmdb_score": 8.0, "tmdb_votes": 1000, "tmdb_popularity": 10.0, "final_score": 10.0,
        "content_rating": "NC-17" if blocked else "PG-13", "keywords": [], "adult": False,
    }


def test_inspector_reports_reason_and_current_gate_without_identifiers(tmp_path: Path) -> None:
    database = tmp_path / "copy.sqlite3"
    blocked = _candidate(blocked=True)
    safe = _candidate(blocked=False)
    save_candidate_pool_dict({"blocked": blocked, "safe": safe}, path=database, purge_watched=False)
    save_current_deck({"deck_id": "private", "active": [blocked], "reserve": []}, path=database)

    result = inspect_database(database, output=tmp_path / "evidence")
    report = result["reports"][0]
    text = (tmp_path / "evidence" / "saved_deck_safety_report.json").read_text(encoding="utf-8")

    assert result["anomaly_count"] == 1
    assert report["stored_safety"]["decision"]["reason_code"] == "explicit_content_rating"
    assert report["current_rebuild"]["candidate_in_active_or_reserve"] is False
    assert "Private title" not in text
    assert "Private overview" not in text
    assert "123" not in text


def test_inspector_keeps_source_database_unchanged(tmp_path: Path) -> None:
    database = tmp_path / "copy.sqlite3"
    save_candidate_pool_dict({"safe": _candidate(blocked=False)}, path=database, purge_watched=False)
    before = database.read_bytes()
    result = inspect_database(database, output=tmp_path / "evidence")
    assert result["anomaly_count"] == 0
    assert database.read_bytes() == before
