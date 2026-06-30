# candidates

Папка `candidates` отвечает за сбор, хранение, импорт, фильтрацию и диагностику общего пула кандидатов для рекомендаций сериалов.

Главная идея: здесь живёт логика candidate pool. UI должен обращаться сюда через `candidates.service`, а не напрямую менять JSON или вызывать низкоуровневые функции.

Desktop GUI visual-polish не должен менять код этой папки. Контракт внешнего вида PyQt GUI описан в [../docs/DESKTOP_STYLE_CONTRACT.md](../docs/DESKTOP_STYLE_CONTRACT.md).

## Основные файлы

`service.py`

Тонкий facade для UI. Через него должны идти консольные сценарии:

- просмотр pool;
- статистика pool;
- search view;
- фильтры search;
- import TMDb result в общий pool;
- build/save TMDb candidate pool;
- retry KP enrichment;
- mark watched/delete/diagnostics;
- очистка дублей и stats с числом уникальных кандидатов.

Если меняется UI flow, сначала ищи подходящую функцию в `service.py` или добавляй новую facade-функцию туда.

`candidate_pool.py`

Работа с общим `candidate_pool.json` и `candidate_criteria.json`:

- чтение/сохранение pool;
- нормализация storage;
- дедуп по `normalized_title|year` (`pool_entry_key`);
- слияние похожих названий одного года (`dedupe_pool_by_similar_titles`);
- явная очистка дублей (`clean_common_pool_duplicates`);
- удаление watched-кандидатов на write-path;
- фильтрация saved pool для search;
- runtime genre matching по уже сохранённым жанрам;
- retry KP для неполных кандидатов;
- диагностика подозрительных дублей;
- расчёт признаков и ранжирование кандидатов.

Важно: `load_candidate_pool()` должен оставаться read-only. Запись происходит через `save_candidate_pool()` и отдельные write-path функции.

`tmdb_candidate_pool.py`

Сбор нового snapshot через TMDb Discover/Details + локальный IMDb SQL + KP enrichment.

Поток:

1. `discover_defaults()`
2. `apply_discover_filters()`
3. `api_tmdb.discover_tv_candidates()`
4. `deduplicate_discover_results()`
5. `remove_watched_discover()`
6. `api_tmdb.get_tv_details()`
7. `prepare_candidate()`
8. `enrich_from_imdb_sql()`
9. `enrich_from_kp_cache_only()`
10. `enrich_from_kp_api_if_needed()`
11. scoring: `quality_score`, `hidden_gem_score`, `final_score`
12. `normalize_tmdb_candidate_for_common_pool()`

Сейчас есть защита от серии сетевых ошибок:

- после 3 подряд ошибок `TMDb Details` следующие Details-запросы пропускаются;
- после 3 подряд ошибок `KP API` следующие KP API-запросы пропускаются;
- прогресс должен сообщать `TMDb Details: Пропущено` или `KP API: Пропущено`.

`import_tmdb.py`

Импорт сохранённого TMDb result JSON в общий `candidate_pool.json`.

Отдельно от build-flow. Не делает новый TMDb Discover. Все импортированные кандидаты попадают в общий pool с `criteria_name = "pool"`.

`schema.py`

Единая схема кандидата:

- default-поля;
- `kp_status`;
- `is_complete`;
- `missing_fields`;
- completeness для search.

Если добавляется новый статус KP, проверь `_PRESERVED_KP_STATUSES`, иначе нормализация может перезаписать статус.

`keys.py`

Стабильные ключи identity:

- `COMMON_POOL_CRITERIA_NAME = "pool"` — единственный named criteria entry;
- `title_identity_key(candidate)` -> `normalized_title|year`;
- `pool_entry_key(candidate)` -> `normalized_title|year` (один общий pool, без criteria в ключе).

Эти ключи важны для дедупа после merge старых пуллов. Не меняй формат без миграции и тестов.

`genres.py`

Runtime normalization/matching жанров уже сохранённого pool:

- RU/EN aliases;
- matching include/exclude для search;
- может знать жанры, которых нет в TMDb TV Discover, например `Триллер`.

Не использовать этот модуль для TMDb Discover genre IDs.

`tmdb_genre_options.py`

Только TMDb TV genre IDs для Discover filters:

- include genres;
- exclude genres;
- OR через `|`;
- AND через `,`;
- labels для UI.

Не добавляй сюда жанры, которых нет в TMDb TV genres. Например, отдельного TV genre ID для `Триллер` нет.

`tmdb_country_options.py`

Список стран для выбора TMDb Discover country в UI:

- ISO-2 code -> русское название;
- порядок показа;
- парсинг номеров стран.

Сейчас build-flow поддерживает одну страну за запуск. Парсер уже умеет несколько номеров, но multi-country build требует отдельного изменения service/build-flow.

`kp_enrichment.py`

Общая логика KP enrichment:

- country mapping ISO-2 -> KP country;
- candidate queries;
- match-check;
- заполнение KP rating/votes/description;
- lookup через KP API.

## Данные и файлы

Основные JSON находятся не в `candidates`, а в data/config paths:

- `constant.CANDIDATE_POOL_JSON` -> общий `candidate_pool.json`;
- `constant.CRITERIA_POOL_JSON` -> `candidate_criteria.json` (одна запись `"pool"` — defaults сбора и search-фильтров);
- TMDb snapshots -> `data/exports/candidate_pool/*.json`;
- diagnostics -> `data/diagnostics`;
- KP cache -> `data/cache/kp`.

## Важные границы

### TMDb Discover genres и saved pool genres разные

TMDb build:

- использует `tmdb_genre_options.py`;
- работает по официальным TMDb TV genre IDs;
- передаёт `with_genres` / `without_genres` в Discover params.

Search:

- использует уже сохранённые жанры кандидата;
- работает через `candidate_pool.py` + `genres.py`;
- не делает новый TMDb-запрос.

### Build snapshot и общий pool разные

`tmdb_candidate_pool.build_candidate_pool()` создаёт snapshot/result.

Чтобы положить результат в общий pool, нужен import:

- `service.import_tmdb_result_to_pool(...)`;
- или `import_tmdb.import_tmdb_result_to_common_pool(...)`.

Не смешивай build и import в низкоуровневом коде без явного UI/service решения.

### Read-path и write-path

Read-only функции не должны менять JSON:

- views в `service.py`;
- `load_candidate_pool()`;
- `get_all_candidates()`;
- filtering для search;
- diagnostics.

Write-path функции могут сохранять:

- `save_candidate_pool()`;
- import TMDb result;
- retry KP enrichment;
- `clean_common_pool_duplicates()` / `clear_common_pool()`;
- mark watched cleanup.

## Единый pool и счётчики

После merge нескольких legacy-пуллов в JSON могут остаться:

- лишние ключи (старый формат `criteria|title|year`);
- exact-дубли одного `title|year`;
- похожие названия одного года;
- cross-year дубли: одно normalized title, год ±1 (с guard по `imdb_id`/`tmdb_id`).

При записи в pool write-path выставляет **канонический год**: `imdb_start_year` > `year` > `kp_year` (`normalize_candidate_for_storage`).

Read-path stats (`get_pool_stats`) показывают:

- `unique_total` — число уникальных кандидатов после нормализации;
- `raw_total` — число записей в JSON;
- `duplicate_entries` — лишние exact-дубли;
- `similar_duplicate_total` — сколько можно слить по похожим названиям;
- `cross_year_duplicate_total` — сколько можно слить по cross-year (±1 год).

Диагностика cross-year (read-only): `find_cross_year_title_groups()` / Console → Диагностика → п.6.

Write-path очистка:

- Console: **Поиск сериалов → Управление pool → Очистить дубли в pool**;
- `service.clean_common_pool_duplicates()`;
- `candidate_pool.clean_common_pool_duplicates()`.

Очистка пересохраняет pool с каноническими ключами и оставляет лучшую запись по рейтингу/полноте.

## Частые задачи

Добавить параметр в TMDb Discover:

1. `tmdb_candidate_pool.build_candidate_pool(...)`
2. `apply_discover_filters(...)`
3. `service.build_tmdb_candidate_pool(...)`
4. UI flow в `ui/console/interface_funcs.py`
5. offline tests в `tests/test.py`

Добавить новый UI-фильтр search:

1. defaults в `candidate_pool.build_search_filter_defaults()`
2. formatter в `format_search_filter_default_lines()`
3. matching в `filter_saved_candidates_for_search()`
4. facade в `service.py`, если нужен
5. UI в `interface_funcs.py`
6. tests без сети

Изменить дедуп/identity:

1. `keys.py`
2. `candidate_pool.deduplicate_pool()` / `dedupe_pool_by_similar_titles()`
3. import paths
4. migration compatibility tests
5. `clean_common_pool_duplicates()` для явной очистки JSON

## Тесты

После изменений в `candidates` обычно запускать:

```powershell
C:\Users\super\AppData\Local\Programs\Python\Python313\python.exe -m compileall main.py common config storage dataset candidates model apis ui scripts tests
C:\Users\super\AppData\Local\Programs\Python\Python313\python.exe tests\test.py
```

Для новых сетевых сценариев добавляй offline-тесты с `patch(...)`. Реальные TMDb/KP запросы в tests не нужны.
