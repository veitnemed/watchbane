# Watchbane SQLite Migration Plan

This document is the storage contract for migrating Watchbane runtime user data
from JSON-first persistence to SQLite-first persistence.

## Target

- SQLite database path: `data/watchbane.sqlite3`.
- SQLite is the source of truth for watched records, watched meta, candidate
  pool, candidate criteria, local hidden/watchlist actions, app settings, and
  poster-cache metadata.
- Runtime UI, desktop, console, and domain code must not issue SQL directly.
  They must use `dataset.service`, `candidates.service`, compatibility
  wrappers, or `storage.sqlite` repositories.
- Public functions keep returning the same dict/list shapes as the legacy JSON
  functions unless a later phase explicitly documents and tests a contract
  change.

## Legacy JSON Rules

Legacy JSON remains supported for:

- initial import into SQLite;
- explicit backup/export from SQLite;
- explicit legacy JSON import/export compatibility;
- tests and migration fixtures.

The app must not automatically delete legacy JSON files. Runtime writes to
watched/candidate/settings/poster metadata JSON are legacy-only once SQLite is
the active backend.

## File-Based Data That Remains

These artifacts stay file-based:

- TMDb cache and export snapshots under `data/exports/` or cache folders;
- poster image files under `data/cache/posters/images`;
- temporary screenshots under `screens/tmp_ui/`;
- explicit JSON backup/export outputs;
- temporary migration files.

Poster image bytes are not stored in SQLite. SQLite stores only poster metadata
and local image paths.

## Current JSON Paths

- Watched dataset: `data/watched/titles.json`
- Watched meta: `data/watched/meta.json`
- Candidate pool: `data/candidates/pool.json`
- Candidate criteria: `data/candidates/criteria.json`
- Candidate watchlist: `data/candidates/watchlist.json`
- Candidate hidden list: `data/candidates/hidden.json`
- App settings: `data/settings.json`
- Poster metadata cache: `data/cache/posters/posters.json`

## Schema Overview

The first schema version uses hybrid tables: indexed columns for common
queries plus canonical JSON payload columns to preserve compatibility.

- `schema_migrations`: applied schema versions.
- `watched_records`: one row per watched title, keyed by `dataset_key`, with
  indexed title/media/year/TMDb/IMDb fields, `payload_json`, and `meta_json`.
- `candidate_records`: one row per candidate, keyed by `pool_key`, with
  indexed criteria, media, year, TMDb, score fields, and `payload_json`.
- `candidate_criteria`: one row per saved criteria object.
- `candidate_actions`: hidden/watchlist entries keyed by stable candidate
  identity and action.
- `app_settings`: JSON value per setting key.
- `poster_cache_entries`: poster metadata per title/year identity.

All app connections must enable `PRAGMA foreign_keys=ON`, WAL mode, a busy
timeout, and `sqlite3.Row` row factory.

## Migration Phases

1. Add the migration contract document.
2. Add SQLite connection helpers and idempotent migration runner.
3. Add schema v1 and schema/index tests.
4. Add JSON extraction and identity helpers.
5. Add watched repository with legacy-compatible shapes.
6. Add candidate repository with legacy-compatible shapes.
7. Add action, settings, and poster metadata repositories.
8. Add idempotent JSON to SQLite importer with dry-run and backups.
9. Add SQLite to JSON exporter.
10. Add backend selection flag with JSON default.
11. Route watched reads through backend adapter.
12. Route watched writes through backend adapter.
13. Route candidate reads through backend adapter.
14. Route candidate writes through backend adapter.
15. Route actions, settings, and poster metadata through backend adapter.
16. Add safe startup migration flow for SQLite backend.
17. Flip default backend to SQLite with JSON override.
18. Add indexed query methods and performance tests.
19. Add SQLite-aware backup/restore safety.
20. Update user and contributor documentation.
21. Add guardrails against direct JSON writes to migrated user data.
22. Run final regression and cleanup.

After these phases, run ten small hardening cycles. Each cycle inspects the new
SQLite architecture, identifies two weak spots, fixes one, adds or updates
tests, and commits the result.

## Legacy JSON Export Plan

- Use the SQLite to JSON exporter to write legacy-compatible JSON files.
- JSON is not a selectable runtime backend after the cleanup cutover.
- Restore a SQLite backup if the database file is damaged.
- Legacy JSON files are never deleted automatically, so first-run import is
  non-destructive.

## Test Plan

Every code phase must run targeted tests, then:

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
```

Important coverage areas:

- SQLite connection pragmas and migration idempotency.
- Schema shape and indexes.
- JSON serialization helpers for old TV-only records, movie-ready records,
  missing optional fields, Unicode titles, and stable identity keys.
- Watched add/update/delete/rename and meta synchronization.
- Candidate pool roundtrip, criteria roundtrip, dedupe compatibility, watched
  cleanup, and Unicode data.
- Hidden/watchlist identity persistence.
- Settings and poster metadata roundtrip.
- JSON import/export idempotency and canonical equivalence.
- Startup import-once behavior.
- SQLite-aware backup/restore.
- Guardrails preventing direct JSON writes outside approved modules.

## UI Boundary Rule

UI modules under `app/`, `desktop/`, `ui/`, and `web/` must not import
`sqlite3`, execute SQL, or know database table names. UI writes must continue
through domain services or existing compatibility wrappers.
