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
    edit_dataset.xlsx
  logs/
    api_requests.log
  backups/
```

## Source Of Truth

- `data/watchbane.sqlite3` - источник правды для runtime user data.
- SQLite хранит watched records, watched meta, candidate pool, candidate criteria, watchlist/hidden actions, app settings и poster-cache metadata.
- JSON-файлы в `data/watched/`, `data/candidates/`, `data/settings.json` и `data/cache/posters/posters.json` являются legacy import/export/backup compatibility, а не source of truth при стандартном backend.
- Для rollback/debug можно запустить legacy backend через `WATCHBANE_STORAGE_BACKEND=json`.

## Runtime Lists

- Watchlist и hidden хранятся в SQLite (`candidate_actions`).
- Legacy JSON-файлы `data/candidates/watchlist.json` и `data/candidates/hidden.json` используются для import/export/rollback.

## Cache

- `data/cache/posters/images/` - локальные poster image files.
- Poster metadata хранится в SQLite и экспортируется в `data/cache/posters/posters.json` только явно.
- `data/cache/tmdb/` - TMDb Discover/Details cache.

Cache можно удалить без потери watched-базы.

## Generated / Exports

- `data/exports/candidate_pool/` - saved TMDb build JSON/CSV.
- `data/exports/edit_dataset.xlsx` - Excel export/import рабочий файл.
- `data/diagnostics/` - diagnostic reports.
- `data/logs/api_requests.log` - API log.
- `data/backups/` - SQLite backups (`*.sqlite3`) и legacy JSON backups/exports.

Generated файлы не хранятся в git.

TMDb-only candidate migration/refresh reports:

- `data/diagnostics/candidate_pool_tmdb_only_migration_report.json`;
- `data/diagnostics/candidate_pool_tmdb_refresh_report.json`.

## Main Info Country

`main_info.country` хранит страну тайтла в watched-записи.

Правила:

- поле текстовое;
- старые записи без `country` нормализуются как пустая строка;
- add-flow подставляет страну из API/SQL/TMDb/candidate;
- если источник не дал страну, используется страна, выбранная пользователем при поиске;
- `country` не участвует в computed scores.

## Git Policy

В git остаются только справочники проекта:

- `config/tags.json`;
- `config/genre_tags.json`;
- `apis/sql_title_aliases.json`.

Локальные runtime data в `data/` игнорируются: SQLite DB, WAL/SHM, legacy JSON, exports, backups и caches не коммитятся.

## Approved Legacy JSON Writers

Direct writes to migrated JSON files are allowed only in compatibility wrappers,
legacy migration/import/export scripts, explicit backup/restore code and tests.
Feature code, UI, desktop, console and service views must route writes through
storage/domain APIs so the active backend can remain SQLite-first.
