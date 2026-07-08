# JSON Runtime Removal Plan

SQLite is the canonical runtime storage. JSON remains only as an explicit
legacy import/export/backup format. This inventory tracks remaining JSON
runtime dependencies after the SQLite migration and orders their deletion.

## Classification

| Area | Current references | Classification | Action |
| --- | --- | --- | --- |
| Runtime backend selector | `storage/backend.py`, `WATCHBANE_STORAGE_BACKEND`, `BACKEND_JSON`, `get_storage_backend()`, `is_sqlite_backend()` | DELETE | Remove env-driven runtime switch. Replace call sites with direct SQLite paths or explicit legacy utility calls. |
| Watched runtime facade | `storage/data.py` JSON branches, `constant.FILE_NAME`, `constant.META_JSON`, `dump_json_atomic`, `is_json_exists` | DELETE | Keep facade API if useful, but make implementation SQLite-only. Move JSON reads/writes to legacy import/export. |
| Candidate runtime repositories | `candidates/repositories/pool_repository.py`, `criteria_repository.py`, `json_io.py` | DELETE | Make repositories SQLite-only or replace callers with split SQLite repositories. Delete JSON persistence helpers. |
| Search lists | `app/core/storage.py`, `watchlist.json`, `hidden.json` | DELETE | Route watchlist/hidden through SQLite action repository only. Keep JSON names only in legacy export/import mappings. |
| Poster runtime cache | `posters/cache.py`, `DEFAULT_POSTER_CACHE_JSON`, `posters.json` | DELETE/MOVE | Runtime metadata should use SQLite. Keep JSON file path only for explicit legacy import/export. |
| Settings runtime | `desktop/settings/app_settings.py`, `config/app_settings_store.py`, `settings.json` | DELETE/MOVE | Runtime settings should use SQLite. Keep JSON handling only for legacy import/export or explicitly documented local config if still required. |
| Startup initialization | `storage/runtime.py`, `tests/test_runtime_init.py`, JSON file creation expectations | DELETE | Startup should create/apply SQLite DB only. It may import existing legacy JSON once, but must not initialize runtime JSON files. |
| Backup/restore | `storage/files.py`, `create_backup()`, `restore_backup()` | KEEP/MOVE | Keep user-facing backup/restore. SQLite backup is runtime path; JSON backup restore stays legacy-only. |
| Legacy import/export | `storage/sqlite/import_legacy.py`, `storage/sqlite/export_legacy.py`, `scripts/migrate_json_to_sqlite.py`, `scripts/export_sqlite_to_json.py` | KEEP/MOVE | Move behind explicit `storage/legacy_json/` namespace or equivalent. No runtime callers except first-run import. |
| Data profiles | `storage/profiles.py`, profile JSON path updates | INVESTIGATE | Profiles may still describe legacy files. Rework after runtime JSON initialization is removed. |
| Direct JSON utilities | `storage/files.dump_json_atomic`, `is_json_exists`, direct `json.load`/`json.dump` in runtime modules | DELETE/MOVE | Delete generic runtime JSON helpers after legacy import/export owns JSON file IO. Keep non-storage JSON uses such as API caches and reports. |
| TMDb/API/report JSON | `apis/*`, `candidates/sources/tmdb/*`, report scripts | KEEP | These are external API caches, diagnostic reports, or output formats, not runtime storage backend. |
| Tests forcing JSON backend | `tests/conftest.py`, `tests/test_storage_backend.py`, JSON read/write tests for runtime files | DELETE | Convert tests to SQLite-first. Keep legacy import/export tests with explicit JSON fixtures. |
| Docs mentioning active JSON | `README.md`, `docs/DATA_STORAGE_PLAN.md`, older architecture docs | DELETE/MOVE | Rewrite docs to say JSON is legacy import/export/backup only. |

## Ordered Deletion Plan

1. Freeze SQLite-only contract tests and baseline the current dependency surface.
2. Remove runtime backend selector and all `WATCHBANE_STORAGE_BACKEND` behavior.
3. Move legacy JSON import/export code into an explicit legacy namespace.
4. Remove JSON file initialization from runtime startup.
5. Convert `storage.data` watched facade to SQLite-only.
6. Convert candidate pool/criteria repositories to SQLite-only and remove `json_io`.
7. Convert settings, poster cache, watchlist, and hidden action paths to SQLite-only.
8. Delete obsolete runtime JSON helper functions and JSON-backend tests.
9. Clean scripts and docs so JSON is described only as legacy import/export/backup.
10. Split large SQLite mapping and repository modules by responsibility.
11. Consolidate transaction ownership helpers used by repositories.
12. Add DB invariants and diagnostics that replace JSON guardrails.
13. Run a final dead-code sweep for backend selector, JSON runtime file names, and old imports.
14. Keep explicit legacy import/export/backup coverage until the cleanup branch is stable.

## Grep Baseline

The initial audit used:

- `rg "WATCHBANE_STORAGE_BACKEND|BACKEND_JSON|is_sqlite_backend|get_storage_backend"`
- `rg "titles\\.json|meta\\.json|pool\\.json|criteria\\.json|settings\\.json|hidden\\.json|watchlist\\.json|posters\\.json"`
- `rg "dump_json_atomic|is_json_exists|create_backup|json\\.load|json\\.dump"`
- `rg "from storage import data|import storage\\.data|from storage\\.data|from storage\\.files|import storage\\.files"`

The remaining matches are expected at this stage. Later prompts should reduce
runtime matches while preserving explicit legacy import/export and backup paths.
