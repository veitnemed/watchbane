# Data Storage Plan

Целевая структура локальных данных `Watchbane`.

```text
data/
  watchbane.sqlite3
  watched/
    titles.json
    meta.json
  candidates/
    pool.json
    criteria.json
    watchlist.json
    hidden.json
  cache/
    posters/
    tmdb/
  exports/
    candidate_pool/
  logs/
    api_requests.log
  backups/
```

## Source Of Truth

- `data/watchbane.sqlite3` - источник правды для runtime user data.
- SQLite хранит watched records, watched meta, candidate pool, candidate criteria, watchlist/hidden actions, app settings и poster-cache metadata.
- JSON-файлы в `data/watched/`, `data/candidates/`, `data/settings.json` и `data/cache/posters/posters.json` являются legacy import/export/backup compatibility, а не source of truth при стандартном backend.
- Runtime backend selector removed: JSON is no longer a selectable runtime backend.
- Legacy JSON path constants живут в `scripts/migrations/legacy_paths.py`, не в `config/constant.py`.

## Runtime Lists

- Watchlist и hidden хранятся в SQLite (`candidate_actions`).
- Legacy JSON-файлы `data/candidates/watchlist.json` и `data/candidates/hidden.json` используются только для import/export compatibility.

## Cache

- `data/cache/posters/images/` - локальные poster image files.
- Poster metadata хранится в SQLite и экспортируется в `data/cache/posters/posters.json` только явно.
- `data/cache/tmdb/` - TMDb Discover/Details cache.

Cache можно удалить без потери watched-базы.

## Generated / Exports

- `data/exports/candidate_pool/` - saved TMDb build JSON/CSV.
- `data/diagnostics/` - diagnostic reports.
- `data/logs/api_requests.log` - API log.
- `data/backups/` - SQLite backups (`*.sqlite3`) и legacy JSON backups/exports.

Generated файлы не хранятся в git.

TMDb-only candidate migration/refresh reports:

- `data/diagnostics/candidate_pool_tmdb_only_migration_report.json`;
- `data/diagnostics/candidate_pool_tmdb_refresh_report.json`.

## SQLite Diagnostics

`storage.sqlite.diagnostics` provides read-only runtime DB diagnostics:

- schema version;
- `PRAGMA quick_check`;
- `PRAGMA foreign_key_check`;
- table counts;
- duplicate watched/candidate title and TMDb identities;
- orphaned candidate actions;
- legacy JSON files that may still exist on disk but are not canonical.

## Main Info Country

`main_info.country` хранит страну тайтла в watched-записи.

Правила:

- поле текстовое;
- старые записи без `country` нормализуются как пустая строка;
- add-flow подставляет страну из TMDb/candidate;
- если источник не дал страну, используется страна, выбранная пользователем при поиске;
- `country` не участвует в computed scores.

## Git Policy

В git остаются только схемы и справочники проекта (`config/scheme.py`, `config/constant.py`, `candidates/models/genre_schema.py`).

Локальные runtime data в `data/` игнорируются: SQLite DB, WAL/SHM, legacy JSON, exports, backups и caches не коммитятся.

## Approved Legacy JSON Writers

Direct writes to migrated JSON files are allowed only in compatibility wrappers,
legacy migration/import/export scripts, explicit backup/restore code and tests.
Feature code, UI, desktop, console and service views must route writes through
storage/domain APIs so the active backend can remain SQLite-first.
