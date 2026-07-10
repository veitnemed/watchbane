from __future__ import annotations

from storage.sqlite import (
    action_repository,
    candidate_repository,
    diagnostics,
    watched_repository,
)


def _movie(title: str, year: int) -> dict:
    return {
        "main_info": {
            "title": title,
            "year": year,
            "user_score": 8,
            "country": "US",
            "media_type": "tv",
        },
        "raw_scores": {},
    }


def test_sqlite_diagnostics_reports_health_and_counts(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    db_path = tmp_path / "watchbane.sqlite3"

    watched_repository.save_dataset_dict({"Dark": _movie("Dark", 2017)}, path=db_path)
    candidate_repository.save_candidate_pool_dict(
        {"dark": {"title": "Dark", "year": 2017}},
        path=db_path,
        purge_watched=False,
    )

    report = diagnostics.build_sqlite_diagnostics(path=db_path, base_dir=tmp_path)

    assert report["schema_version"] == 3
    assert report["quick_check_ok"] is True
    assert report["foreign_key_check_ok"] is True
    assert report["table_counts"]["watched_records"] == 1
    assert report["table_counts"]["candidate_records"] == 1
    assert report["duplicates"]["watched_title_identity"] == []
    assert report["duplicates"]["candidate_title_identity"] == []


def test_sqlite_diagnostics_reports_duplicate_identities(tmp_path, monkeypatch) -> None:
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations

    monkeypatch.setattr("storage.data.load_dataset", lambda: {})
    db_path = tmp_path / "watchbane.sqlite3"
    watched_repository.save_dataset_dict(
        {
            "Dark A": _movie("Dark", 2017),
            "Dark B": _movie("Dark", 2017),
        },
        path=db_path,
    )
    candidate_repository.save_candidate_pool_dict(
        {
            "a": {"title": "Dark", "year": 2017, "tmdb_id": 1},
            "b": {"title": "Dark", "year": 2017, "tmdb_id": 2},
        },
        path=db_path,
        purge_watched=False,
    )
    conn = connect(db_path)
    try:
        apply_migrations(conn)
        conn.execute(
            """
            INSERT INTO candidate_records(
              pool_key, title, title_normalized, media_type, year, tmdb_id,
              payload_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "dark-duplicate",
                "Dark",
                "dark",
                "tv",
                2017,
                3,
                '{"title":"Dark","year":2017}',
                "2026-01-01T00:00:00",
                "2026-01-01T00:00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    report = diagnostics.build_sqlite_diagnostics(path=db_path, base_dir=tmp_path)

    assert report["duplicates"]["watched_title_identity"][0]["count"] == 2
    assert report["duplicates"]["candidate_title_identity"][0]["count"] == 2


def test_sqlite_diagnostics_reports_orphaned_actions_and_legacy_json(tmp_path) -> None:
    db_path = tmp_path / "watchbane.sqlite3"
    action_repository.add_candidate_action(
        action_repository.ACTION_HIDDEN,
        {"title": "Ghost", "year": 2020},
        path=db_path,
    )
    data_dir = tmp_path / "data"
    legacy_files = [
        data_dir / "watched" / "titles.json",
        data_dir / "candidates" / "watchlist.json",
        data_dir / "candidates" / "hidden.json",
        data_dir / "cache" / "posters" / "posters.json",
    ]
    for legacy_file in legacy_files:
        legacy_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_file.write_text("{}", encoding="utf-8")

    report = diagnostics.build_sqlite_diagnostics(path=db_path, base_dir=data_dir)

    assert report["orphaned_candidate_actions"] == [
        {"action": action_repository.ACTION_HIDDEN, "identity_key": "ghost|2020"}
    ]
    assert report["legacy_json_files"] == [
        {
            "path": "watched/titles.json",
            "exists": True,
            "canonical": False,
            "size_bytes": 2,
        },
        {
            "path": "candidates/watchlist.json",
            "exists": True,
            "canonical": False,
            "size_bytes": 2,
        },
        {
            "path": "candidates/hidden.json",
            "exists": True,
            "canonical": False,
            "size_bytes": 2,
        },
        {
            "path": "cache/posters/posters.json",
            "exists": True,
            "canonical": False,
            "size_bytes": 2,
        },
    ]
