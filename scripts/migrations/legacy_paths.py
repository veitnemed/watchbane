"""Legacy JSON path constants for migration/import/export scripts only."""

from __future__ import annotations

APP_DATA_DIR = "data"
WATCHED_DIR = f"{APP_DATA_DIR}/watched"
CANDIDATES_DIR = f"{APP_DATA_DIR}/candidates"

FILE_NAME = f"{WATCHED_DIR}/titles.json"
META_JSON = f"{WATCHED_DIR}/meta.json"
CANDIDATE_POOL_JSON = f"{CANDIDATES_DIR}/pool.json"
CRITERIA_POOL_JSON = f"{CANDIDATES_DIR}/criteria.json"

LEGACY_JSON_MARKERS = (
    FILE_NAME,
    META_JSON,
    CANDIDATE_POOL_JSON,
    CRITERIA_POOL_JSON,
    f"{WATCHED_DIR}/watchlist.json",
    f"{WATCHED_DIR}/hidden.json",
    f"{CANDIDATES_DIR}/watchlist.json",
    f"{CANDIDATES_DIR}/hidden.json",
    f"{APP_DATA_DIR}/cache/posters/posters.json",
)
