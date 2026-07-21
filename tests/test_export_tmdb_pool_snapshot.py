from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import hashlib

import pytest
from jsonschema import Draft202012Validator

from config.app_paths import get_app_paths
from tools.research.export_tmdb_pool_snapshot import ExportError, export_snapshot, main, resolve_source


ROOT = Path(__file__).resolve().parents[1]


def _db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE candidate_records (
          pool_key TEXT PRIMARY KEY, title TEXT NOT NULL, title_normalized TEXT NOT NULL,
          media_type TEXT NOT NULL, year INTEGER, tmdb_id INTEGER, criteria_name TEXT,
          tmdb_score REAL, tmdb_votes INTEGER, tmdb_popularity REAL, quality_score REAL,
          hidden_gem_score REAL, final_score REAL, payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE candidate_actions (identity_key TEXT, action TEXT, candidate_json TEXT, created_at TEXT);
        CREATE TABLE candidate_impressions (identity_key TEXT, media_type TEXT, shown_count INTEGER, first_shown_at TEXT, last_shown_at TEXT, last_deck_id TEXT);
        CREATE TABLE watched_records (dataset_key TEXT, media_type TEXT, tmdb_id INTEGER);
        CREATE TABLE recommendation_deck_state (singleton_id INTEGER, deck_id TEXT, state_json TEXT, updated_at TEXT);
        """
    )
    conn.close()
    return path


def _payload(**overrides: object) -> dict:
    value = {
        "tmdb_id": 101,
        "media_type": "tv",
        "title": "Russian title",
        "original_title": "Original title",
        "overview": "Russian overview",
        "year": 2020,
        "adult": False,
        "content_rating": "16+",
        "keywords": ["drama"],
        "country_codes": ["RU"],
        "episode_run_time": [24, 48],
        "tmdb_score": 8.1,
        "tmdb_votes": 100,
        "watch_providers": ["Fixture stream"],
        "poster_path": "/poster.jpg",
        "actors_top": [{"name": "Actor"}],
        "crew_top": [{"name": "Director"}],
    }
    value.update(overrides)
    return value


def _insert(conn: sqlite3.Connection, key: str, payload: object, *, media_type: str = "tv", tmdb_id: int | None = 101, score: float = 8.1) -> None:
    conn.execute(
        "INSERT INTO candidate_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (key, "Stored title", "stored title", media_type, 2020, tmdb_id, None, score, 100, 4.0, 1.0, 0.0, 2.0, json.dumps(payload) if not isinstance(payload, str) else payload, "now", "now"),
    )


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_export_movie_tv_legacy_and_diagnostics(tmp_path: Path) -> None:
    database = _db(tmp_path / "copy.db")
    conn = sqlite3.connect(database)
    _insert(conn, "tv", _payload())
    _insert(conn, "movie", _payload(tmdb_id=202, media_type="movie", title="Movie", runtime=120), media_type="movie", tmdb_id=202)
    _insert(conn, "legacy", _payload(tmdb_id=None, title="Legacy"), tmdb_id=None)
    _insert(conn, "bad", "{broken", tmdb_id=303)
    _insert(conn, "conflict", _payload(tmdb_id=404, tmdb_score=1.0), tmdb_id=404, score=9.0)
    conn.execute("INSERT INTO candidate_actions VALUES (?, ?, ?, ?)", ("tv:tmdb:101", "watchlist", "{}", "now"))
    conn.execute("INSERT INTO recommendation_deck_state VALUES (1, 'deck', ?, 'now')", (json.dumps({"active": [_payload()], "reserve": []}),))
    conn.commit(); conn.close()

    source_hash = _hash(database)
    source_mtime = database.stat().st_mtime_ns
    result = export_snapshot(database, tmp_path / "evidence")

    assert result["records"] == 5
    snapshots = _lines(tmp_path / "evidence" / "pool_snapshot.jsonl")
    assert len(snapshots) == 5
    tv = next(item for item in snapshots if item["tmdb_id"] == 101)
    assert tv["raw_api"]["status"] == "not_available_in_local_snapshot"
    assert tv["layers"]["normalized"]["source"] == "reconstructed_from_stored_payload"
    assert tv["saved_state"]["active"] is True
    assert tv["saved_state"]["watchlist"] is True
    legacy = next(item for item in snapshots if item["tmdb_id"] is None)
    assert legacy["identity_reliability"] == "legacy"
    assert any(item["kind"] == "invalid_json" for item in _lines(tmp_path / "evidence" / "anomalies.jsonl"))
    assert any(item["kind"] == "sql_payload_conflict" for item in _lines(tmp_path / "evidence" / "anomalies.jsonl"))
    assert "Russian title" not in (tmp_path / "evidence" / "pool_snapshot.csv").read_text(encoding="utf-8")
    assert _hash(database) == source_hash
    assert database.stat().st_mtime_ns == source_mtime
    summary = json.loads((tmp_path / "evidence" / "summary.json").read_text(encoding="utf-8"))
    assert summary["tv"]["missing_runtime"] == 1  # malformed TV payload is included in the aggregate.


def test_duplicate_is_reported_and_schema_validates(tmp_path: Path) -> None:
    database = _db(tmp_path / "copy.db")
    conn = sqlite3.connect(database)
    _insert(conn, "one", _payload())
    _insert(conn, "two", _payload(title="Other"))
    conn.commit(); conn.close()

    export_snapshot(database, tmp_path / "evidence")
    snapshots = _lines(tmp_path / "evidence" / "pool_snapshot.jsonl")
    assert len(snapshots) == 1
    assert any(item["kind"] == "duplicate_identity" for item in _lines(tmp_path / "evidence" / "anomalies.jsonl"))
    schema = json.loads((ROOT / "research" / "tmdb" / "schema.json").read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(snapshots[0]))


def test_empty_database_and_source_validation(tmp_path: Path) -> None:
    database = _db(tmp_path / "copy.db")
    result = export_snapshot(database, tmp_path / "evidence")
    assert result["exported"] == 0
    assert _lines(tmp_path / "evidence" / "pool_snapshot.jsonl") == []
    with pytest.raises(ExportError, match="exactly one"):
        resolve_source(database=None, runtime_root=None)
    with pytest.raises(ExportError, match="does not exist"):
        resolve_source(database=tmp_path / "missing.db", runtime_root=None)
    with pytest.raises(SystemExit):
        main(["--output", str(tmp_path / "evidence")])
    with pytest.raises(ExportError, match="production runtime"):
        resolve_source(database=get_app_paths().database_path, runtime_root=None)
