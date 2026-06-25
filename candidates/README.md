# candidates

Папка `candidates` отвечает за сбор, хранение, импорт, фильтрацию и диагностику общего пула кандидатов для рекомендаций сериалов.

Главная идея: здесь живёт логика candidate pool. UI должен обращаться сюда через `candidates.service`, а не напрямую менять JSON или вызывать низкоуровневые функции.

Desktop GUI visual-polish не должен менять код этой папки. Контракт внешнего вида PyQt GUI описан в [../docs/DESKTOP_STYLE_CONTRACT.md](../docs/DESKTOP_STYLE_CONTRACT.md).

## Основные файлы

`service.py`

Тонкий facade для UI. Через него должны идти консольные сценарии:

- просмотр pool;
- статистика pool;
- top prediction view;
- фильтры top prediction;
- import TMDb result в общий pool;
- build/save TMDb candidate pool;
- retry KP enrichment;
- mark watched/delete/diagnostics.

Если меняется UI flow, сначала ищи подходящую функцию в `service.py` или добавляй новую facade-функцию туда.

`candidate_pool.py`

Работа с общим `candidate_pool.json` и `candidate_criteria.json`:

- чтение/сохранение pool;
- нормализация storage;
- дедуп по `criteria_name + title + year`;
- удаление watched-кандидатов на write-path;
- фильтрация saved pool для top prediction;
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

Отдельно от build-flow. Не делает новый TMDb Discover. Сохраняет/мерджит metadata criteria и добавляет кандидатов в общий pool.

`schema.py`

Единая схема кандидата:

- default-поля;
- `kp_status`;
- `is_complete`;
- `missing_fields`;
- readiness для prediction.

Если добавляется новый статус KP, проверь `_PRESERVED_KP_STATUSES`, иначе нормализация может перезаписать статус.

`keys.py`

Стабильные ключи identity:

- `title_identity_key(candidate)` -> `normalized_title|year`;
- `pool_entry_key(candidate)` -> `criteria_name|normalized_title|year`.

Эти ключи важны для дедупа и cross-criteria хранения. Не меняй формат без миграции и тестов.

`genres.py`

Runtime normalization/matching жанров уже сохранённого pool:

- RU/EN aliases;
- matching include/exclude для top prediction;
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
- `constant.CRITERIA_POOL_JSON` -> `candidate_criteria.json`;
- TMDb snapshots -> `data/candidate_pool/*.json`;
- diagnostics -> `data/diagnostics`;
- KP cache -> `data/cache/kp`.

## Важные границы

### TMDb Discover genres и saved pool genres разные

TMDb build:

- использует `tmdb_genre_options.py`;
- работает по официальным TMDb TV genre IDs;
- передаёт `with_genres` / `without_genres` в Discover params.

Top prediction:

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
- filtering для top prediction;
- diagnostics.

Write-path функции могут сохранять:

- `save_candidate_pool()`;
- import TMDb result;
- retry KP enrichment;
- delete criteria/candidates;
- mark watched cleanup.

## Частые задачи

Добавить параметр в TMDb Discover:

1. `tmdb_candidate_pool.build_candidate_pool(...)`
2. `apply_discover_filters(...)`
3. `service.build_tmdb_candidate_pool(...)`
4. UI flow в `ui/console/interface_funcs.py`
5. offline tests в `tests/test.py`

Добавить новый UI-фильтр top prediction:

1. defaults в `candidate_pool.build_prediction_filter_defaults()`
2. formatter в `format_prediction_filter_default_lines()`
3. matching в `filter_saved_candidates_for_prediction()`
4. facade в `service.py`, если нужен
5. UI в `interface_funcs.py`
6. tests без сети

Изменить дедуп/identity:

1. `keys.py`
2. `candidate_pool.deduplicate_pool()`
3. import paths
4. cross-criteria tests
5. migration compatibility

## Тесты

После изменений в `candidates` обычно запускать:

```powershell
C:\Users\super\AppData\Local\Programs\Python\Python313\python.exe -m compileall main.py common config storage dataset candidates model apis ui scripts tests
C:\Users\super\AppData\Local\Programs\Python\Python313\python.exe tests\test.py
```

Для новых сетевых сценариев добавляй offline-тесты с `patch(...)`. Реальные TMDb/KP запросы в tests не нужны.
