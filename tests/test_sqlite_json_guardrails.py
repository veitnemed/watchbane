from __future__ import annotations

from pathlib import Path


APPROVED_DIRECT_JSON_WRITERS = {
    "app/core/storage.py",
    "candidates/repositories/criteria_repository.py",
    "candidates/repositories/json_io.py",
    "candidates/repositories/pool_repository.py",
    "desktop/settings/app_settings.py",
    "posters/cache.py",
    "storage/data.py",
    "storage/files.py",
    "storage/legacy_json/exporter.py",
    "storage/legacy_json/importer.py",
    "scripts/export_sqlite_to_json.py",
    "scripts/migrate_json_to_sqlite.py",
    "scripts/migrate_candidate_pool_tmdb_only.py",
    "scripts/migrate_watched_raw_scores_tmdb_only.py",
    "scripts/refresh_candidate_pool_from_tmdb.py",
    "scripts/refresh_watched_from_tmdb.py",
    "dataset/migrations/data_language.py",
    "dataset/migrations/tmdb_localized.py",
    "storage/profiles.py",
}

MIGRATED_STORAGE_MARKERS = (
    "FILE_NAME",
    "META_JSON",
    "CANDIDATE_POOL_JSON",
    "CRITERIA_POOL_JSON",
    "APP_SETTINGS_JSON",
    "watchlist.json",
    "hidden.json",
    "posters.json",
    "data/watched/titles.json",
    "data/watched/meta.json",
    "data/candidates/pool.json",
    "data/candidates/criteria.json",
)

WRITE_MARKERS = (
    "json.dump",
    "dump_json_atomic",
    ".write_text(",
    ".open(\"w\"",
    ".open('w'",
    "open(path, \"w\"",
    "open(path, 'w'",
)


def test_no_unapproved_direct_json_writes_to_migrated_runtime_data() -> None:
    findings: set[tuple[str, str]] = set()
    for root in ("app", "candidates", "config", "dataset", "desktop", "posters", "scripts", "storage", "ui", "web"):
        for path in Path(root).rglob("*.py"):
            normalized = path.as_posix()
            if normalized in APPROVED_DIRECT_JSON_WRITERS:
                continue
            source = path.read_text(encoding="utf-8")
            if not any(marker in source for marker in MIGRATED_STORAGE_MARKERS):
                continue
            if not any(marker in source for marker in WRITE_MARKERS):
                continue
            findings.add((normalized, "direct migrated JSON write marker"))

    assert findings == set()
