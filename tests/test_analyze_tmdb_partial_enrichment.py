from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from config.app_paths import get_app_paths
from tools.research.analyze_tmdb_partial_enrichment import analyze_database, main
from tools.research.export_tmdb_pool_snapshot import ExportError, resolve_source


def _database(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE candidate_records (
          pool_key TEXT PRIMARY KEY, media_type TEXT, tmdb_id INTEGER,
          tmdb_score REAL, tmdb_votes INTEGER, source TEXT, source_bucket_id TEXT,
          payload_json TEXT NOT NULL, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE candidate_autofill_requests (
          onboarding_profile_id INTEGER, bucket_id TEXT, endpoint TEXT, status TEXT,
          accepted_count INTEGER, rejected_count INTEGER
        );
        """
    )
    conn.close()
    return path


def _payload(*, full: bool = False, marker: object = False, source: str = "onboarding_autofill", version: int = 3, bucket: str = "bucket", profile: int = 1) -> dict:
    payload = {
        "media_type": "movie", "tmdb_id": 1, "source": source,
        "source_version": version, "source_bucket_id": bucket,
        "onboarding_profile_id": profile, "details_enriched": marker,
        "source_query": {"origin": "foreign"}, "is_complete": True,
    }
    if full:
        payload.update({"runtime": 120, "content_rating": "16+", "keywords": ["drama"]})
    return payload


def _insert(conn: sqlite3.Connection, key: str, payload: object, *, score: float = 8.0) -> None:
    conn.execute(
        "INSERT INTO candidate_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (key, "movie", 1, score, 10, "onboarding_autofill", "bucket", json.dumps(payload) if not isinstance(payload, str) else payload, "created", "updated"),
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reports_split_cohorts_and_historical_contract_verdict(tmp_path: Path) -> None:
    database = _database(tmp_path / "copy.db")
    conn = sqlite3.connect(database)
    _insert(conn, "partial", _payload(marker=True))
    _insert(conn, "full", _payload(full=True, marker=False))
    _insert(conn, "mixed", {**_payload(), "runtime": 90})
    _insert(conn, "bad", "{")
    conn.execute("INSERT INTO candidate_autofill_requests VALUES (1, 'bucket', '/discover/movie', 'ok', 10, 0)")
    conn.commit(); conn.close()
    source_hash, source_mtime = _digest(database), database.stat().st_mtime_ns

    result = analyze_database(database, output=tmp_path / "evidence")

    assert result["cohorts"]["full"]["records"] == 1
    assert result["cohorts"]["partial"]["records"] == 1
    assert result["cohorts"]["mixed"]["records"] == 1
    assert result["cohorts"]["invalid"]["records"] == 1
    assert result["verdict"]["primary_category"] == "E_different_acquisition_or_historical_contract"
    assert result["verdict"]["details_enriched_reliability"] == "not_reliable"
    assert result["path_contract"]["onboarding_discover_details"]["copies_traced_fields"] == []
    assert json.loads((tmp_path / "evidence" / "run_manifest.json").read_text())["read_only_proof"] is True
    assert "foreign" not in (tmp_path / "evidence" / "cohort_summary.json").read_text(encoding="utf-8")
    assert _digest(database) == source_hash
    assert database.stat().st_mtime_ns == source_mtime


def test_empty_database_is_inconclusive(tmp_path: Path) -> None:
    result = analyze_database(_database(tmp_path / "copy.db"), output=tmp_path / "evidence")
    assert result["cohorts"]["full"]["records"] == 0
    assert result["verdict"]["primary_category"] == "inconclusive"


def test_different_source_version_does_not_claim_shared_historical_contract(tmp_path: Path) -> None:
    database = _database(tmp_path / "copy.db")
    conn = sqlite3.connect(database)
    _insert(conn, "partial", _payload(version=3))
    _insert(conn, "full", _payload(full=True, version=4))
    conn.commit(); conn.close()

    result = analyze_database(database, output=tmp_path / "evidence")

    assert result["verdict"]["primary_category"] == "inconclusive"


def test_rejects_production_database_and_requires_database() -> None:
    with pytest.raises(ExportError, match="production runtime"):
        resolve_source(database=get_app_paths().database_path, runtime_root=None)
    with pytest.raises(SystemExit):
        main([])
