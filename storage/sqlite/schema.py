"""SQLite schema migrations."""

from __future__ import annotations

import sqlite3


def apply_v1(conn: sqlite3.Connection) -> None:
    """Create the initial hybrid SQLite schema."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS watched_records (
          dataset_key TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          title_normalized TEXT NOT NULL,
          media_type TEXT NOT NULL DEFAULT 'tv',
          year INTEGER,
          user_score REAL,
          country TEXT,
          tmdb_id INTEGER,
          imdb_id TEXT,
          payload_json TEXT NOT NULL,
          meta_json TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_watched_title_norm
          ON watched_records(title_normalized);
        CREATE INDEX IF NOT EXISTS idx_watched_media_year
          ON watched_records(media_type, year);
        CREATE INDEX IF NOT EXISTS idx_watched_tmdb
          ON watched_records(media_type, tmdb_id);
        CREATE INDEX IF NOT EXISTS idx_watched_imdb
          ON watched_records(imdb_id);

        CREATE TABLE IF NOT EXISTS candidate_records (
          pool_key TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          title_normalized TEXT NOT NULL,
          media_type TEXT NOT NULL DEFAULT 'tv',
          year INTEGER,
          tmdb_id INTEGER,
          criteria_name TEXT,
          tmdb_score REAL,
          tmdb_votes INTEGER,
          tmdb_popularity REAL,
          quality_score REAL,
          hidden_gem_score REAL,
          final_score REAL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_candidate_criteria
          ON candidate_records(criteria_name);
        CREATE INDEX IF NOT EXISTS idx_candidate_media_year
          ON candidate_records(media_type, year);
        CREATE INDEX IF NOT EXISTS idx_candidate_scores
          ON candidate_records(final_score DESC, quality_score DESC, tmdb_score DESC);
        CREATE INDEX IF NOT EXISTS idx_candidate_title_norm
          ON candidate_records(title_normalized);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_candidate_tmdb_unique
          ON candidate_records(media_type, tmdb_id)
          WHERE tmdb_id IS NOT NULL;

        CREATE TABLE IF NOT EXISTS candidate_criteria (
          criteria_name TEXT PRIMARY KEY,
          criteria_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS candidate_actions (
          identity_key TEXT NOT NULL,
          action TEXT NOT NULL,
          candidate_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(identity_key, action)
        );
        CREATE INDEX IF NOT EXISTS idx_candidate_actions_action
          ON candidate_actions(action);

        CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY,
          value_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS poster_cache_entries (
          identity_key TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          year INTEGER,
          poster_path TEXT,
          poster_url TEXT,
          local_path TEXT,
          status TEXT,
          source TEXT,
          payload_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_poster_cache_title_year
          ON poster_cache_entries(title, year);
        """
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column in _table_columns(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def apply_v2(conn: sqlite3.Connection) -> None:
    """Add deterministic onboarding candidate-autofill storage."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS onboarding_profiles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ui_language TEXT NOT NULL,
          media_preference TEXT NOT NULL,
          release_preference TEXT NOT NULL,
          vibe_preference TEXT NOT NULL,
          origin_preference TEXT,
          created_at TEXT NOT NULL,
          completed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_onboarding_profiles_completed
          ON onboarding_profiles(completed_at);

        CREATE TABLE IF NOT EXISTS candidate_autofill_requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          onboarding_profile_id INTEGER NOT NULL,
          bucket_id TEXT NOT NULL,
          endpoint TEXT NOT NULL,
          params_json TEXT NOT NULL,
          page INTEGER NOT NULL,
          status TEXT NOT NULL,
          accepted_count INTEGER NOT NULL DEFAULT 0,
          rejected_count INTEGER NOT NULL DEFAULT 0,
          error_text TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY(onboarding_profile_id) REFERENCES onboarding_profiles(id)
        );

        CREATE INDEX IF NOT EXISTS idx_candidate_autofill_profile
          ON candidate_autofill_requests(onboarding_profile_id);
        CREATE INDEX IF NOT EXISTS idx_candidate_autofill_bucket
          ON candidate_autofill_requests(bucket_id);
        """
    )

    _add_column_if_missing(conn, "candidate_records", "source", "TEXT")
    _add_column_if_missing(conn, "candidate_records", "source_bucket_id", "TEXT")
    _add_column_if_missing(conn, "candidate_records", "onboarding_profile_id", "INTEGER")
    _add_column_if_missing(conn, "candidate_records", "candidate_score", "REAL")
    _add_column_if_missing(conn, "candidate_records", "fetch_rank", "INTEGER")

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_candidate_source
          ON candidate_records(source);
        CREATE INDEX IF NOT EXISTS idx_candidate_onboarding_profile
          ON candidate_records(onboarding_profile_id);
        CREATE INDEX IF NOT EXISTS idx_candidate_autofill_score
          ON candidate_records(candidate_score DESC, fetch_rank ASC);
        """
    )


def apply_v3(conn: sqlite3.Connection) -> None:
    """Add FTS5 search index over deterministic candidate documents."""
    conn.executescript(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS candidate_fts USING fts5(
          pool_key UNINDEXED,
          document,
          tokenize='unicode61 remove_diacritics 2'
        );
        """
    )


def apply_v4(conn: sqlite3.Connection) -> None:
    """Add recommendation impression history independent from user actions."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS candidate_impressions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          identity_key TEXT NOT NULL,
          media_type TEXT NOT NULL,
          shown_count INTEGER NOT NULL DEFAULT 0,
          first_shown_at TEXT NOT NULL,
          last_shown_at TEXT NOT NULL,
          last_deck_id TEXT,
          UNIQUE(identity_key, media_type)
        );

        CREATE INDEX IF NOT EXISTS idx_candidate_impressions_last_shown
          ON candidate_impressions(last_shown_at);
        """
    )

