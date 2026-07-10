from pathlib import Path

from config import constant
from storage import profiles
from storage import runtime
from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations


def test_ensure_runtime_data_layout_initializes_sqlite_without_runtime_json(monkeypatch, tmp_path) -> None:
    watched_dir = tmp_path / "watched"
    candidates_dir = tmp_path / "candidates"
    cache_dir = tmp_path / "cache"
    exports_dir = tmp_path / "exports"
    logs_dir = tmp_path / "logs"
    backups_dir = tmp_path / "backups"

    titles_json = watched_dir / "titles.json"
    meta_json = watched_dir / "meta.json"
    pool_json = candidates_dir / "pool.json"
    criteria_json = candidates_dir / "criteria.json"
    watchlist_json = candidates_dir / "watchlist.json"
    hidden_json = candidates_dir / "hidden.json"

    monkeypatch.setattr(constant, "APP_DATA_DIR", str(tmp_path))
    profiles.set_base_data_dir(tmp_path)
    monkeypatch.setattr(constant, "WATCHED_DIR", str(watched_dir))
    monkeypatch.setattr(constant, "CANDIDATES_DIR", str(candidates_dir))
    monkeypatch.setattr(constant, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(constant, "EXPORTS_DIR", str(exports_dir))
    monkeypatch.setattr(constant, "LOGS_DIR", str(logs_dir))
    monkeypatch.setattr(constant, "BACKUP_DIR", str(backups_dir))
    monkeypatch.setattr(constant, "DATA_DIR", str(watched_dir))
    monkeypatch.setattr(constant, "DIR_META", str(watched_dir))
    monkeypatch.setattr(constant, "FILE_NAME", str(titles_json))
    monkeypatch.setattr(constant, "META_JSON", str(meta_json))
    monkeypatch.setattr(constant, "CANDIDATE_POOL_JSON", str(pool_json))
    monkeypatch.setattr(constant, "CRITERIA_POOL_JSON", str(criteria_json))
    monkeypatch.setattr(
        runtime,
        "RUNTIME_DIRECTORIES",
        (
            str(tmp_path),
            str(watched_dir),
            str(candidates_dir),
            str(cache_dir),
            str(exports_dir),
            str(logs_dir),
            str(backups_dir),
        ),
    )

    result = runtime.ensure_runtime_data_layout()

    assert result["ok"] is True
    assert result["backup_created"] is False
    assert result["backend"] == "sqlite"
    assert result["sqlite_schema_version"] == 3
    assert (tmp_path / "watchbane.sqlite3").is_file()
    for path in (titles_json, meta_json, pool_json, criteria_json, watchlist_json, hidden_json):
        assert path.exists() is False


def test_dev_empty_profile_flag_backs_up_and_removes_runtime_db(monkeypatch, tmp_path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    db_path = data_root / "watchbane.sqlite3"
    conn = connect(db_path)
    try:
        apply_migrations(conn)
        with conn:
            conn.execute(
                "INSERT INTO candidate_records(pool_key, media_type, tmdb_id, title, title_normalized, year, payload_json, created_at, updated_at) "
                "VALUES('movie|1', 'movie', 1, 'One', 'one', 2020, '{}', 'now', 'now')"
            )
    finally:
        conn.close()

    monkeypatch.setattr(constant, "APP_DATA_DIR", str(data_root))
    profiles.set_base_data_dir(data_root)
    monkeypatch.setenv(runtime.DEV_EMPTY_PROFILE_ENV, "1")
    monkeypatch.delenv(runtime.DEV_CLEAR_CANDIDATES_ENV, raising=False)

    result = runtime.apply_dev_startup_reset_from_env()

    assert result["applied"] is True
    assert result["empty_profile"] is True
    assert Path(result["backup_path"]).is_dir()
    assert db_path.exists() is False


def test_dev_clear_candidates_flag_does_not_clear_watched(monkeypatch, tmp_path) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setattr(constant, "APP_DATA_DIR", str(data_root))
    profiles.set_base_data_dir(data_root)
    runtime.ensure_runtime_data_layout()
    conn = connect(data_root / "watchbane.sqlite3")
    try:
        with conn:
            conn.execute(
                "INSERT INTO watched_records(media_type, title, title_normalized, year, payload_json, created_at, updated_at) "
                "VALUES('movie', 'Kept', 'kept', 2020, '{}', 'now', 'now')"
            )
            conn.execute(
                "INSERT INTO candidate_records(pool_key, media_type, tmdb_id, title, title_normalized, year, payload_json, created_at, updated_at) "
                "VALUES('movie|1', 'movie', 1, 'Removed', 'removed', 2020, '{}', 'now', 'now')"
            )
    finally:
        conn.close()

    monkeypatch.delenv(runtime.DEV_EMPTY_PROFILE_ENV, raising=False)
    monkeypatch.setenv(runtime.DEV_CLEAR_CANDIDATES_ENV, "1")

    result = runtime.apply_dev_startup_reset_from_env()

    conn = connect(data_root / "watchbane.sqlite3")
    try:
        watched = conn.execute("SELECT COUNT(*) AS count FROM watched_records").fetchone()["count"]
        candidates = conn.execute("SELECT COUNT(*) AS count FROM candidate_records").fetchone()["count"]
    finally:
        conn.close()
    assert result["applied"] is True
    assert watched == 1
    assert candidates == 0
