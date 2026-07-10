"""Legacy JSON path constants for migration/import/export scripts only."""

from __future__ import annotations

from pathlib import Path

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


def watched_titles_json(app_data_dir: str | Path | None = None) -> Path:
    """Return legacy watched titles.json path for the given data root."""
    base = Path(app_data_dir) if app_data_dir is not None else Path(APP_DATA_DIR)
    return base / "watched" / "titles.json"


def watched_meta_json(app_data_dir: str | Path | None = None) -> Path:
    """Return legacy watched meta.json path for the given data root."""
    base = Path(app_data_dir) if app_data_dir is not None else Path(APP_DATA_DIR)
    return base / "watched" / "meta.json"


def candidate_pool_json(app_data_dir: str | Path | None = None) -> Path:
    """Return legacy candidate pool.json path for the given data root."""
    base = Path(app_data_dir) if app_data_dir is not None else Path(APP_DATA_DIR)
    return base / "candidates" / "pool.json"


def candidate_criteria_json(app_data_dir: str | Path | None = None) -> Path:
    """Return legacy candidate criteria.json path for the given data root."""
    base = Path(app_data_dir) if app_data_dir is not None else Path(APP_DATA_DIR)
    return base / "candidates" / "criteria.json"


def legacy_json_paths_for_data_root(app_data_dir: str | Path) -> tuple[Path, ...]:
    """Return profile-aware legacy JSON paths for diagnostics."""
    base = Path(app_data_dir)
    return (
        watched_titles_json(base),
        watched_meta_json(base),
        candidate_pool_json(base),
        candidate_criteria_json(base),
        base / "candidates" / "watchlist.json",
        base / "candidates" / "hidden.json",
        base / "cache" / "posters" / "posters.json",
    )
