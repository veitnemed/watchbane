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

