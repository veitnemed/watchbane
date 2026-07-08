# JSON Runtime Removal Plan

SQLite is the canonical runtime storage. JSON remains only as an explicit
legacy import/export/backup format. This inventory tracks remaining JSON
runtime dependencies after the SQLite migration and orders their deletion.

## Classification

| Area | Current references | Classification | Action |
| --- | --- | --- | --- |
| Runtime backend selector | `storage/backend.py`, `WATCHBANE_STORAGE_BACKEND`, `BACKEND_JSON`, `get_storage_backend()`, `is_sqlite_backend()` | DELETE | Remove env-driven runtime switch. Replace call sites with direct SQLite paths or explicit legacy utility calls. |
| Watched runtime facade | `storage/data.py` legacy JSON branches, `constant.FILE_NAME`, `constant.META_JSON` | DELETE | Keep facade API if useful, but make implementation SQLite-only. Move JSON reads/writes to legacy import/export. Generic JSON helpers were deleted. |
| Candidate runtime repositories | `candidates/repositories/pool_repository.py`, `criteria_repository.py`, deleted `json_io.py` | DELETE | Active repositories are SQLite-only. Runtime JSON persistence helper was removed; remaining JSON references are legacy import/export or later cleanup targets. |
| Search lists | `app/core/storage.py`, legacy `watchlist.json`, `hidden.json` | DELETE | Watchlist/hidden route through SQLite action repository only. JSON names remain only in legacy export/import mappings and docs/tests that assert absence. |
| Poster runtime cache | `posters/cache.py`, `DEFAULT_POSTER_CACHE_JSON`, `posters.json` | DELETE/MOVE | Runtime metadata should use SQLite. Keep JSON file path only for explicit legacy import/export. |
| Settings runtime | `desktop/settings/app_settings.py`, `config/app_settings_store.py`, legacy `settings.json` | DELETE/MOVE | Runtime settings use SQLite. JSON handling remains only in legacy import/export compatibility. |
| Startup initialization | `storage/runtime.py`, `tests/test_runtime_init.py`, JSON file creation expectations | DELETE | Startup creates/applies SQLite DB only. Existing legacy JSON requires explicit import and runtime must not initialize JSON files. |
| Backup/restore | `storage/files.py`, `create_backup()`, `restore_backup()` | KEEP/MOVE | Keep user-facing backup/restore. SQLite backup is runtime path; JSON backup restore stays legacy-only. |
| Legacy import/export | `storage/legacy_json/importer.py`, `storage/legacy_json/exporter.py`, `scripts/migrate_json_to_sqlite.py`, `scripts/export_sqlite_to_json.py` | KEEP/MOVE | Keep behind explicit `storage/legacy_json/` namespace. Runtime startup does not call it automatically. Deprecated `storage/sqlite/*_legacy.py` shims exist only for compatibility during cleanup. |
| Data profiles | `storage/profiles.py`, profile JSON path updates | INVESTIGATE | Profiles may still describe legacy files. Rework after runtime JSON initialization is removed. |
| Direct JSON utilities | deleted `storage/files.dump_json_atomic`, deleted `is_json_exists`, direct `json.load`/`json.dump` in runtime modules | DELETE/MOVE | Generic runtime JSON helpers are removed; explicit legacy import/export owns remaining storage JSON file IO. Keep non-storage JSON uses such as API caches and reports. |
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

## Metrics Baseline

Captured before runtime JSON deletion with:

```powershell
py scripts\json_cleanup_metrics.py --json
```

| Metric | Baseline |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15805 |
| Product JSON runtime reference count | 135 |
| Product backend switch reference count | 45 |

After prompt 03 runtime backend selector removal:

| Metric | Prompt 03 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15535 |
| Product JSON runtime reference count | 96 |
| Product backend switch reference count | 0 |

After prompt 04 legacy JSON namespace move:

| Metric | Prompt 04 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15529 |
| Product JSON runtime reference count | 96 |
| Product backend switch reference count | 0 |

After prompt 05 runtime JSON initialization cleanup:

| Metric | Prompt 05 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15518 |
| Product JSON runtime reference count | 96 |
| Product backend switch reference count | 0 |

After prompt 07 candidate JSON helper deletion:

| Metric | Prompt 07 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15499 |
| Product JSON runtime reference count | 92 |
| Product backend switch reference count | 0 |

After prompt 08 settings and search-list cleanup:

| Metric | Prompt 08 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15478 |
| Product JSON runtime reference count | 83 |
| Product backend switch reference count | 0 |

After prompt 09 obsolete JSON helper deletion:

| Metric | Prompt 09 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15452 |
| Product JSON runtime reference count | 77 |
| Product backend switch reference count | 0 |

After prompt 11 SQLite mapping split:

| Metric | Prompt 11 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15251 |
| Product JSON runtime reference count | 77 |
| Product backend switch reference count | 0 |

After prompt 12 watched SQLite repository split:

| Metric | Prompt 12 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15140 |
| Product JSON runtime reference count | 77 |
| Product backend switch reference count | 0 |

After prompt 13 candidate SQLite repository split:

| Metric | Prompt 13 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15323 |
| Product JSON runtime reference count | 77 |
| Product backend switch reference count | 0 |

After prompt 14 transaction ownership consolidation:

| Metric | Prompt 14 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15595 |
| Product JSON runtime reference count | 77 |
| Product backend switch reference count | 0 |

After prompt 15 SQLite diagnostics:

| Metric | Prompt 15 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15595 |
| Product JSON runtime reference count | 77 |
| Product backend switch reference count | 0 |

After prompt 16 SQLite-first test cleanup:

| Metric | Prompt 16 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15734 |
| Product JSON runtime reference count | 84 |
| Product backend switch reference count | 0 |

Prompt 16 JSON reference count includes read-only SQLite diagnostics that report
legacy JSON files as non-canonical artifacts.

After prompt 17 final docs cleanup:

| Metric | Prompt 17 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15734 |
| Product JSON runtime reference count | 84 |
| Product backend switch reference count | 0 |

Prompt 17 updated public docs to describe SQLite as canonical runtime storage
and legacy JSON as explicit import/export/backup compatibility.

After prompt 18 final dead-code sweep:

| Metric | Prompt 18 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15716 |
| Product JSON runtime reference count | 77 |
| Product backend switch reference count | 0 |

Deleted dead compatibility shims from `storage/sqlite/` and kept legacy JSON
behind `storage/legacy_json/`, `storage/files.py` backup/restore compatibility,
and explicit migration/repair scripts.

After prompt 19 storage/service boundary hardening:

| Metric | Prompt 19 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15703 |
| Product JSON runtime reference count | 77 |
| Product backend switch reference count | 0 |

Moved app-core local action routing behind `storage/actions.py` so `app/core`
does not import SQLite internals directly.

After prompt 20 candidate transfer hardening:

| Metric | Prompt 20 |
| --- | ---: |
| Tracked Python LOC under `storage`, `candidates`, `dataset`, `app/core` | 15799 |
| Product JSON runtime reference count | 77 |
| Product backend switch reference count | 0 |

Added atomic watched dataset+meta persistence for add/candidate transfer and
stopped poster side effects from reloading meta by title after the save.
