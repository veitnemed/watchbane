# Отчёт: Search Step 6 — SQL pre-filter + FTS join

- Дата: 2026-07-10
- Пул: 662 кандидата (production SQLite)
- Предыдущий этап: [otchet_poisk_step5_calibration.md](otchet_poisk_step5_calibration.md) (precision@10 **0.617**)

## Цель

Убрать загрузку всего пула (662 payload) на каждый текстовый запрос: FTS + indexed structural filters в SQL, точечная загрузка hits, Python-фильтры для genre/country/watched.

## Архитектура

```mermaid
flowchart LR
  sqlFts["search_fts_prefiltered + JOIN"]
  loadHits["load_candidate_records_by_pool_keys"]
  pyFilter["filter_candidates: genre/country/watched"]
  rerank["rank + attach_text_relevance"]
  sqlFts --> loadHits --> pyFilter --> rerank
```

### Новые модули

| Модуль | Назначение |
|--------|------------|
| [`candidates/search/structural_sql.py`](../../candidates/search/structural_sql.py) | `build_structural_sql_filters()` → SQL на `candidate_records` |
| [`candidates/search/fts_index.py`](../../candidates/search/fts_index.py) | `search_fts_prefiltered()` — `candidate_fts MATCH` + JOIN |
| [`storage/sqlite/candidate_query_repository.py`](../../storage/sqlite/candidate_query_repository.py) | `load_candidate_records_by_pool_keys()` |
| [`candidates/service.py`](../../candidates/service.py) | SQL path в `search_candidate_pool_text()`; fallback на legacy intersect |

### SQL vs Python

| Фильтр | Где |
|--------|-----|
| `media_type`, `year_min/max`, `min_tmdb_score`, `min_final_score`, `criteria_name`, `source` | SQL JOIN |
| `country`, `include/exclude_genres`, `only_unwatched`, `hide_hidden`, `min_tmdb_votes`, `only_complete` | Python (`app/core/filters.py`) |

## Benchmark (production, 40 cases × 5 repeats)

Команда:

```powershell
py scripts/reports/benchmark_search_fts.py --repeats 5
```

| Метрика | Legacy (full pool + intersect) | SQL path |
|---------|-------------------------------|----------|
| p50 latency | **482 ms** | **4 ms** |
| p95 latency | 537 ms | 137 ms |
| mean latency | 436 ms | 33 ms |

`legacy_count` == `sql_count` во всех 40 кейсах — parity по количеству результатов.

Узкие запросы (`комедия`, `фантастика`, ~150–200 hits): SQL path ~100–140 ms vs ~500 ms legacy — выигрыш за счёт отказа от полной загрузки пула.

## Fallback

- `OperationalError` при точечной загрузке → legacy intersect с переданным списком candidates.
- Пустой FTS после prefilter → plain `search_fts` + legacy intersect.

## Проверки

```powershell
py -m pytest tests/test_search_document.py tests/test_candidate_fts_index.py tests/test_search_fts_integration.py tests/desktop/test_candidate_search_behavior.py tests/test_search_query_log.py tests/test_ui_scale_settings.py::test_save_then_load_fts_search_setting -q
```

Результат: **47 passed**.

## UX

Без изменений desktop UI; `CandidateSearchWorker` по-прежнему логирует `latency_ms`.
