from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from tools.research.create_tmdb_real_pool_snapshot import SnapshotBlocked, create_snapshot, fingerprint, _sidecar_metadata


def _wal_database(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE candidate_records (id INTEGER PRIMARY KEY, payload_json TEXT NOT NULL)")
    conn.execute("INSERT INTO candidate_records(payload_json) VALUES ('{}')")
    conn.commit()
    conn.close()
    return path


def test_online_backup_creates_consistent_copy_without_changing_source(tmp_path: Path) -> None:
    source = _wal_database(tmp_path / "watchbane.sqlite3")
    before_stat = source.stat()
    snapshot, report = create_snapshot(source, tmp_path / "evidence")

    assert snapshot.is_file()
    assert report["source_unchanged"] is True
    assert source.stat().st_size == before_stat.st_size
    assert source.stat().st_mtime_ns == before_stat.st_mtime_ns
    target = sqlite3.connect(f"{snapshot.as_uri()}?mode=ro", uri=True)
    try:
        assert target.execute("SELECT COUNT(*) FROM candidate_records").fetchone()[0] == 1
    finally:
        target.close()


def test_snapshot_refuses_missing_source(tmp_path: Path) -> None:
    with pytest.raises(SnapshotBlocked, match="not found"):
        create_snapshot(tmp_path / "missing.sqlite3", tmp_path / "evidence")


def test_fingerprint_includes_wal_shm_and_readonly_pragmas(tmp_path: Path) -> None:
    source = _wal_database(tmp_path / "watchbane.sqlite3")
    conn = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
    try:
        report = fingerprint(source, conn)
    finally:
        conn.close()
    assert {"sha256", "size_bytes", "mtime_ns", "wal_shm", "user_version", "page_count", "data_version"} <= set(report)
    assert set(_sidecar_metadata(source)) == {"wal", "shm"}
