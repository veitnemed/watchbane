from __future__ import annotations

from storage.sqlite.connection import connect
from storage.sqlite.migrations import apply_migrations, get_current_schema_version


EXPECTED_TABLES = {
    "schema_migrations",
    "watched_records",
    "candidate_records",
    "candidate_criteria",
    "candidate_actions",
    "app_settings",
    "poster_cache_entries",
    "onboarding_profiles",
    "candidate_autofill_requests",
}


def _columns(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _indexes(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA index_list({table})")}


def test_schema_creates_expected_tables_and_columns(tmp_path) -> None:
    conn = connect(tmp_path / "watchbane.sqlite3")
    try:
        assert apply_migrations(conn) == 2

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert EXPECTED_TABLES.issubset(tables)
        assert get_current_schema_version(conn) == 2

        assert {
            "dataset_key",
            "title",
            "title_normalized",
            "media_type",
            "year",
            "user_score",
            "country",
            "tmdb_id",
            "imdb_id",
            "payload_json",
            "meta_json",
            "created_at",
            "updated_at",
        }.issubset(_columns(conn, "watched_records"))

        assert {
            "pool_key",
            "title",
            "title_normalized",
            "media_type",
            "year",
            "tmdb_id",
            "criteria_name",
            "tmdb_score",
            "tmdb_votes",
            "tmdb_popularity",
            "quality_score",
            "hidden_gem_score",
            "final_score",
            "source",
            "source_bucket_id",
            "onboarding_profile_id",
            "candidate_score",
            "fetch_rank",
            "payload_json",
            "created_at",
            "updated_at",
        }.issubset(_columns(conn, "candidate_records"))

        assert {
            "id",
            "ui_language",
            "media_preference",
            "release_preference",
            "vibe_preference",
            "origin_preference",
            "created_at",
            "completed_at",
        }.issubset(_columns(conn, "onboarding_profiles"))

        assert {
            "id",
            "onboarding_profile_id",
            "bucket_id",
            "endpoint",
            "params_json",
            "page",
            "status",
            "accepted_count",
            "rejected_count",
            "error_text",
            "created_at",
        }.issubset(_columns(conn, "candidate_autofill_requests"))
    finally:
        conn.close()


def test_schema_creates_query_indexes(tmp_path) -> None:
    conn = connect(tmp_path / "watchbane.sqlite3")
    try:
        apply_migrations(conn)

        assert {
            "idx_watched_title_norm",
            "idx_watched_media_year",
            "idx_watched_tmdb",
            "idx_watched_imdb",
        }.issubset(_indexes(conn, "watched_records"))
        assert {
            "idx_candidate_criteria",
            "idx_candidate_media_year",
            "idx_candidate_scores",
            "idx_candidate_title_norm",
            "idx_candidate_tmdb_unique",
            "idx_candidate_source",
            "idx_candidate_onboarding_profile",
            "idx_candidate_autofill_score",
        }.issubset(_indexes(conn, "candidate_records"))
        assert "idx_poster_cache_title_year" in _indexes(conn, "poster_cache_entries")
        assert "idx_onboarding_profiles_completed" in _indexes(conn, "onboarding_profiles")
        assert "idx_candidate_autofill_profile" in _indexes(conn, "candidate_autofill_requests")
    finally:
        conn.close()
