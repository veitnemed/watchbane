"""Synthetic persisted profiles built with each historical schema prefix."""
import json
from contextlib import closing

import pytest

from storage.sqlite.connection import connect
from storage.sqlite.migrations import MIGRATIONS, apply_migrations
from storage.sqlite.startup import ensure_sqlite_startup_migration


def _read_profile(db):
    with closing(connect(db)) as conn:
        watched = [tuple(row) for row in conn.execute("""
            SELECT dataset_key, title, media_type, year, tmdb_id, imdb_id,
                   user_score, payload_json, meta_json, created_at, updated_at
            FROM watched_records ORDER BY dataset_key
        """)]
        actions = [tuple(row) for row in conn.execute("""
            SELECT identity_key, action, candidate_json, created_at
            FROM candidate_actions ORDER BY identity_key
        """)]
        settings = [tuple(row) for row in conn.execute("""
            SELECT key, value_json, updated_at FROM app_settings ORDER BY key
        """)]
        history = [tuple(row) for row in conn.execute("""
            SELECT version, name FROM schema_migrations ORDER BY version
        """)]
        assert [row[0] for row in conn.execute("PRAGMA integrity_check")] == ["ok"]
        return watched, actions, settings, history


@pytest.mark.parametrize("old_version", range(1, 6))
def test_real_older_profiles_upgrade_without_reidentification_or_repeat_conversion(tmp_path, old_version):
    db = tmp_path / "watchbane.sqlite3"
    created = "2025-02-01T12:00:00Z"
    updated = "2025-02-02T12:00:00Z"
    old_score = 7.9 if old_version < 5 else 2
    with closing(connect(db)) as conn:
        assert apply_migrations(conn, migrations=MIGRATIONS[:old_version]) == old_version
        # Same localized title, year and numeric TMDb ID; types and IMDb IDs distinguish them.
        for kind, imdb in (("movie", "tt100001"), ("tv", "tt100002")):
            main = {"title": "Тёзки", "media_type": kind, "user_score": old_score, "watched_at": "2025-02-01"}
            raw = {"tmdb_id": 777, "imdb_id": imdb}
            conn.execute("""
                INSERT INTO watched_records(
                    dataset_key, title, title_normalized, media_type, year, tmdb_id,
                    imdb_id, user_score, payload_json, meta_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"legacy-{kind}", "Тёзки", "тёзки", kind, 2020, 777, imdb, old_score,
                  json.dumps({"main_info": main, "raw_scores": raw}, ensure_ascii=False),
                  json.dumps({"note": f"Метка {kind}"}, ensure_ascii=False), created, updated))
        for kind, action, date_tag in (("movie", "watchlist", "added_at"), ("tv", "hidden", "hidden_at")):
            candidate = {"title": "Другие тёзки", "year": 2021, "tmdb_id": 778, "media_type": kind}
            conn.execute("""
                INSERT INTO candidate_actions(identity_key, action, candidate_json, created_at)
                VALUES (?, ?, ?, ?)
            """, (f"другие тёзки|2021|{kind}", action,
                  json.dumps({"candidate": candidate, date_tag: created}, ensure_ascii=False), created))
        conn.execute("INSERT INTO app_settings(key, value_json, updated_at) VALUES (?, ?, ?)",
                     ("ui_scale", "1.25", updated))
        conn.commit()

    before = _read_profile(db)
    assert len(before[0]) == 2 and len(before[1]) == 2 and len(before[2]) == 1
    assert ensure_sqlite_startup_migration(base_dir=tmp_path, db_path=db)["schema_version"] == 6
    after = _read_profile(db)
    for old, new in zip(before[0], after[0], strict=True):
        assert new[:6] == old[:6]
        assert new[6] == 2 and type(new[6]) is int
        payload = json.loads(old[7])
        payload["main_info"]["user_score"] = 2
        assert json.loads(new[7]) == payload
        assert new[8:] == old[8:]
    assert after[1:3] == before[1:3]
    assert after[3] == [(m.version, m.name) for m in MIGRATIONS]

    backups = list((tmp_path / "backups" / "migrations").glob("*.sqlite3"))
    if old_version < 5:
        assert len(backups) == 1
        backup = _read_profile(backups[0])
        assert backup[:3] == before[:3]
        # The v5 safety copy is taken after earlier migrations, but before score conversion.
        assert backup[3] == [(m.version, m.name) for m in MIGRATIONS[:4]]
    else:
        assert not backups

    assert ensure_sqlite_startup_migration(base_dir=tmp_path, db_path=db)["schema_version"] == 6
    assert _read_profile(db) == after
    assert list((tmp_path / "backups" / "migrations").glob("*.sqlite3")) == backups
