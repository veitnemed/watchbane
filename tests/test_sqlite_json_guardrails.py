from __future__ import annotations

from pathlib import Path


APPROVED_DIRECT_JSON_WRITERS = {
    "app/core/storage.py",
    "candidates/repositories/criteria_repository.py",
    "candidates/repositories/pool_repository.py",
    "posters/cache.py",
    "storage/data.py",
    "storage/files.py",
    "storage/legacy_json/exporter.py",
    "storage/legacy_json/importer.py",
    "tools/migrations/export_sqlite_to_json.py",
    "tools/migrations/migrate_json_to_sqlite.py",
    "tools/migrations/migrate_candidate_pool_tmdb_only.py",
    "tools/migrations/migrate_watched_raw_scores_tmdb_only.py",
    "tools/migrations/strip_watched_tags_vibe.py",
    "tools/migrations/strip_watched_genre_section.py",
    "tools/migrations/strip_candidate_kp_imdb_fields.py",
    "tools/tmdb/refresh_candidate_pool_from_tmdb.py",
    "tools/tmdb/refresh_watched_from_tmdb.py",
    "dataset/migrations/data_language.py",
    "dataset/migrations/tmdb_localized.py",
    "storage/profiles.py",
}

from tools.migrations.legacy_paths import LEGACY_JSON_MARKERS

MIGRATED_STORAGE_MARKERS = LEGACY_JSON_MARKERS + (
    "watchlist.json",
    "hidden.json",
    "posters.json",
)

WRITE_MARKERS = (
    "json.dump",
    ".write_text(",
    ".open(\"w\"",
    ".open('w'",
    "open(path, \"w\"",
    "open(path, 'w'",
)


def test_no_unapproved_direct_json_writes_to_migrated_runtime_data() -> None:
    findings: set[tuple[str, str]] = set()
    for root in ("app", "candidates", "config", "dataset", "desktop", "posters", "storage", "tools", "ui", "web"):
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


def test_legacy_json_import_export_stays_out_of_sqlite_namespace() -> None:
    assert Path("storage/sqlite/import_legacy.py").exists() is False
    assert Path("storage/sqlite/export_legacy.py").exists() is False

    findings: set[str] = set()
    for root in ("app", "candidates", "config", "dataset", "desktop", "posters", "scripts", "storage", "ui", "web"):
        for path in Path(root).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "storage.sqlite.import_legacy" in source or "storage.sqlite.export_legacy" in source:
                findings.add(path.as_posix())

    assert findings == set()
