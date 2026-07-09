# candidates

Папка `candidates` отвечает за сбор, хранение, импорт, фильтрацию и диагностику общего пула кандидатов для рекомендаций сериалов и фильмов.

Главная идея: здесь живёт логика candidate pool. UI должен обращаться сюда через `candidates.service`, а не напрямую менять SQLite/legacy JSON или вызывать низкоуровневые функции.

Desktop GUI visual-polish не должен менять код этой папки. Контракт внешнего вида PyQt GUI описан в [../docs/DESKTOP_STYLE_CONTRACT.md](../docs/DESKTOP_STYLE_CONTRACT.md).

## Структура пакета

```
candidates/
  service.py              # facade для UI и console
  genres.py, to_dataset.py

  models/                 # schema, keys, country_schema, genre_schema
  repositories/           # SQLite-backed load/save pool и criteria
  pool/                   # dedupe, queries, stats, diagnostics, search_helpers, completeness
  scoring/                # sort keys
  search/                 # FTS document, index, rerank, query log
  views/                  # formatters
  sources/
    tmdb/                 # discovery, details, normalizer, scoring, builder, output, importer
```

Новый код импортирует из `models/`, `pool/`, `repositories/`, `sources/`. UI — через `service.py`.

## Основные модули

### `service.py`

Facade для UI и console: pool view/stats, search, TMDb build/import, dedupe, diagnostics.

### `models/`

- `schema.py` — нормализация, TMDb-only completeness.
- `keys.py` — `title_identity_key`, `pool_entry_key`, `COMMON_POOL_CRITERIA_NAME`.
- `country_schema.py`, `genre_schema.py` — canonical keys в pool record.

### `repositories/`

- `load_candidate_pool()` — read-only raw dict.
- `save_candidate_pool()` — normalize + purge watched на write-path.

### `pool/`

normalization, dedupe, watched_cleanup, dataset_overlap, queries, stats, diagnostics, search_helpers, completeness.

### `sources/tmdb/`

Build pipeline: discovery slices → TMDb Discover API → merge/dedupe → TMDb Details → `normalizer` → `scoring` → `builder` → `output` (JSON/CSV). Import snapshot: `importer`.

### Top-level без переноса

- `genres.py` — runtime matching жанров saved pool (не TMDb Discover IDs).
- `to_dataset.py` — mapper pool genres → dataset `has_*`.

## Данные и файлы

- runtime candidate pool и criteria → `data/watchbane.sqlite3`
- legacy import/export compatibility → `data/candidates/pool.json`, `data/candidates/criteria.json`
- TMDb snapshots → `data/exports/candidate_pool/*.json`
- diagnostics → `data/diagnostics`
- TMDb cache/runtime exports → `data/cache/tmdb`, `data/exports/candidate_pool`

## Важные границы

### TMDb Discover genres и saved pool genres разные

TMDb build: `sources/tmdb/genre_options.py` + TMDb TV/movie genre IDs.

Search: сохранённые жанры кандидата через `pool/search_helpers.py` + `genres.py`.

### Build snapshot и общий pool разные

`sources/tmdb/builder.build_candidate_pool()` создаёт snapshot.

Import в общий pool: `service.import_tmdb_result_to_pool(...)` или `sources/tmdb/importer`.

### Read-path и write-path

Read-only: `service` views, `load_candidate_pool()`, `get_all_candidates()`, diagnostics.

Write-path: `save_candidate_pool()`, import, dedupe, clear pool.

## Единый pool и счётчики

Ключ identity: TV/legacy `normalized_title|year`, movie `normalized_title|year|movie` (`pool_entry_key`). Write-path: канонический год через `normalize_candidate_for_storage`.

Stats: `pool/stats.get_pool_stats()` — `unique_total`, `raw_total`, duplicate counters.

Очистка дублей: `service.clean_common_pool_duplicates()` / `pool/dedupe.clean_common_pool_duplicates()`.

## Частые задачи

TMDb Discover параметр: `sources/tmdb/discover_query.py` → `builder` → `service` → console UI.

Search filter: `pool/search_helpers.py` → `service` → `app/core/filters.py`.

Локальный текстовый поиск (Steps 2–6):
- `search/document.py` — детерминированный `search_document` для FTS.
- `search/fts_index.py` — SQLite FTS5 (`candidate_fts`, migration v3), BM25; `search_fts_prefiltered()` — JOIN с `candidate_records` для indexed structural filters.
- `search/structural_sql.py` — маппинг runtime filters → SQL (`media_type`, `year`, scores, `criteria_name`, `source`).
- `service.search_candidate_pool_text()` — FTS retrieval + structural filters; загрузка payload только для FTS hits (`load_candidate_records_by_pool_keys`). **Включён по умолчанию** (`fts_search_enabled=True`); отключение — в desktop Settings. Env override: `WATCHBANE_FTS_SEARCH=0` / `=1`.
- `search/rerank.py` — combined score (`relevance` sort mode).
- `search/query_log.py` — opt-in JSONL (`WATCHBANE_LOG_SEARCH_QUERIES=1`).
- Offline: `scripts/reports/rebuild_candidate_fts_index.py`, `export_search_top_results.py`, `evaluate_search_relevance.py`, `benchmark_search_fts.py`.

Dedupe/keys: `models/keys.py` → `pool/dedupe.py` → migration tests.

## Тесты

```powershell
py -m compileall candidates
py -m pytest tests/candidate_modules tests/test_search_core.py tests/test_filter_popularity.py -q
```

Offline-тесты с `patch(...)`; без реальных TMDb-запросов.
