import json

from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations, ensure_schema_migrations_table, get_current_schema_version
from storage.sqlite.schema import apply_v1, apply_v2, apply_v3, apply_v4


def test_user_rating_migration_updates_column_and_payload_once(tmp_path) -> None:
    db_path = tmp_path / "ratings.sqlite3"
    conn = connect(db_path)
    try:
        for apply in (apply_v1, apply_v2, apply_v3, apply_v4):
            apply(conn)
        ensure_schema_migrations_table(conn)
        conn.execute(
            """
            INSERT INTO watched_records(
              dataset_key, title, title_normalized, media_type, year, user_score,
              payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "alpha",
                "Alpha",
                "alpha",
                "movie",
                2020,
                7.9,
                json.dumps({"main_info": {"title": "Alpha", "user_score": 7.9}}),
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
            ),
        )
        for version, name in ((1, "initial_schema_v1"), (2, "onboarding_candidate_autofill_v2"), (3, "candidate_fts_v3"), (4, "candidate_impressions_v4")):
            conn.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, "2026-01-01T00:00:00Z"),
            )
        conn.commit()

        assert apply_migrations(conn) == 6
        row = conn.execute("SELECT user_score, payload_json FROM watched_records").fetchone()
        assert row["user_score"] == 2
        assert isinstance(row["user_score"], int)
        assert json.loads(row["payload_json"])["main_info"]["user_score"] == 2
        assert get_current_schema_version(conn) == 6
        assert apply_migrations(conn) == 6
        assert list((tmp_path / "backups" / "migrations").glob("*.sqlite3"))
    finally:
        conn.close()
