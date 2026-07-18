# Карта проекта

`Watchbane` — локальный Python-проект для ведения watched-базы и поиска сериалов/тайтлов через TMDb-only candidate pool.

Старая ML-модель перенесена в `archive/legacy/model/` и не является активной частью runtime.

## Быстрый вход

- [README.md](../../README.md) — пользовательское описание проекта.
- [LOGICAL_ARCHITECTURE.md](LOGICAL_ARCHITECTURE.md) — логические зоны проекта без физического переноса файлов.
- [STRUCTURE_PLAN.md](../../internal/archive/docs/plans/STRUCTURE_PLAN.md) — план структурной чистки.
- [REFACTORING_CHECKLIST.md](REFACTORING_CHECKLIST.md) — чеклист безопасного завершения рефакторинга.
- [DATA_STORAGE_PLAN.md](../../internal/archive/docs/plans/DATA_STORAGE_PLAN.md) — структура локального хранения данных.
- [WORKSPACE_HOUSEKEEPING.md](../operations/WORKSPACE_HOUSEKEEPING.md) — правила для временных скриншотов, локальных кэшей и больших generated-артефактов.
- [add_functions.md](../project/add_functions.md) — правила добавления и изменения функционала.
- [ADD_RECORD_RULES.md](../contracts/ADD_RECORD_RULES.md) — контракт добавления и изменения записей.
- [DESKTOP_STYLE_CONTRACT.md](../contracts/DESKTOP_STYLE_CONTRACT.md) — визуальный контракт desktop GUI.
- [DESKTOP_MODULE_MAP.md](../desktop/DESKTOP_MODULE_MAP.md) — карта модулей desktop и правила расширения.
- [PRODUCT_ROADMAP_CONTRACT.md](../contracts/PRODUCT_ROADMAP_CONTRACT.md) — канон продукта и roadmap фаз.
- [DESKTOP_GUI_ROADMAP.md](../../internal/archive/docs/plans/DESKTOP_GUI_ROADMAP.md) — SUPERSEDED; модульный historical reference.
- [TMDB_ONLY_CANDIDATE_FLOW.md](../contracts/TMDB_ONLY_CANDIDATE_FLOW.md) — TMDb-only candidate contract, migration, refresh и scoring.

## Слои

Физически папки остаются как сейчас. Логически проект делится на 4 зоны:

- `UI`: `app/`, `desktop/`, `ui/`, `web/`;
- `Domain`: `dataset/`, `candidates/`, `posters/`;
- `Infra`: `apis/`, `storage/`, `config/`, `common/`;
- `Project`: `tests/`, `docs/`, `scripts/`, `assets/`.

Runtime/legacy-папки `data/`, `datasets/`, `diagnostics/`, `reports/`, `archive/` не считаются архитектурными зонами.
Подробные правила: [LOGICAL_ARCHITECTURE.md](LOGICAL_ARCHITECTURE.md).

```text
common <- config <- storage <- dataset / apis <- candidates <- ui
```

Правила:

- нижние слои не импортируют UI;
- `apis` только получают внешние данные и не пишут в dataset/pool;
- `candidates` не вызывает `input()` и `print()`, прогресс отдаёт наверх;
- UI не пишет storage напрямую, а вызывает сервисы. Legacy JSON доступен только через explicit import/export/backup.

## Runtime-поток

1. `start_console.py` или `start_app.py` запускает приложение.
2. `storage` инициализирует базовые файлы и каталоги.
3. `ui.console` или `desktop` собирает пользовательский сценарий.
4. `dataset` работает с watched-записями, meta и аналитикой.
5. `candidates` строит и фильтрует candidate pool.
6. `apis` отдаёт данные внешних и локальных источников для сервисов.
7. `posters` синхронизирует poster-cache и локальные изображения.

## Папки

### `app/`

Входные сценарии приложения и общая инициализация.

### `desktop/`

PyQt desktop GUI для watched-базы, карточки тайтла, поиска кандидатов и настроек.

Структура пакетов: [DESKTOP_MODULE_MAP.md](../desktop/DESKTOP_MODULE_MAP.md).

- [desktop/app.py](../../desktop/app.py) — главное окно (shell, вкладки).
- [desktop/watched/](../../desktop/watched/) — watched feature (`model`, `tab`, dialogs).
- [desktop/shared/detail/](../../desktop/shared/detail/) — detail card widget.
- [desktop/candidates/](../../desktop/candidates/) — candidate search (`session`, `filters_view`, `list_view`, `presenters`).
- [desktop/analytics/](../../desktop/analytics/) — внутренние/незарегистрированные analytics helpers; активной вкладки «Информация» нет.
- [desktop/shared/widgets/](../../desktop/shared/widgets/) — переиспользуемые виджеты (sliders, search, chips).
- [desktop/theme/](../../desktop/theme/) — tokens и QSS builders (`tokens.py`, `styles/`).

### `ui/console/`

Консольный интерфейс, меню, prompts и сценарии пользователя.

- [ui/console/console_app.py](../../ui/console/console_app.py) — запуск console UI.
- [ui/console/ui.py](../../ui/console/ui.py) — отрисовка меню.
- [ui/console/global_menu.py](../../ui/console/global_menu.py) — тонкая маршрутизация top-level разделов.
- [ui/console/maintenance_menu.py](../../ui/console/maintenance_menu.py) — главный maintenance hub: состояние, backup, metadata/cache, diagnostics.
- [ui/console/watched_menu.py](../../ui/console/watched_menu.py) — просмотренное: show/rename/delete/add.
- [ui/console/pool_menu.py](../../ui/console/pool_menu.py) — candidate pool: view/search/mark watched, cleanup, import/build.
- [ui/console/search_hub_menu.py](../../ui/console/search_hub_menu.py) — read-only поиск и инспекция.
- [ui/console/reference_menu.py](../../ui/console/reference_menu.py) — справочники dataset.
- [ui/console/interface_funcs.py](../../ui/console/interface_funcs.py) — compatibility facade и оставшиеся watched-сценарии.
- [ui/console/api_tools.py](../../ui/console/api_tools.py) — диагностика TMDb API.
- [ui/console/poster_tools.py](../../ui/console/poster_tools.py) — обслуживание watched metadata и poster-cache.
- [ui/console/candidate_pool_tools.py](../../ui/console/candidate_pool_tools.py) — обслуживание и диагностика общего candidate pool.
- [ui/console/tmdb_pool_tools.py](../../ui/console/tmdb_pool_tools.py) — TMDb build/import flow для candidate pool.
- [ui/console/request.py](../../ui/console/request.py) — формы и prompts.
- [ui/console/search_menu.py](../../ui/console/search_menu.py) — поиск по candidate pool.
- [ui/console/candidate_pool_ui.py](../../ui/console/candidate_pool_ui.py) — настройки сбора и defaults общего pool.
- [ui/console/backup_menu.py](../../ui/console/backup_menu.py) — backup и restore.

### `dataset/`

Watched dataset: добавление, обновление, удаление, meta, статистика и аналитика.

- [dataset/dataset_records.py](../../dataset/dataset_records.py) — центральный add/update service.
- [dataset/storage_movie.py](../../dataset/storage_movie.py) — сбор payload и сохранение записи.
- [dataset/delete_record.py](../../dataset/delete_record.py) — безопасное удаление watched-записи.
- [dataset/title_resolve.py](../../dataset/title_resolve.py) — thin facade для TMDb-only add-title и переноса кандидата.
- [dataset/dataset_stats.py](../../dataset/dataset_stats.py) — сводка dataset.
- [dataset/genre_stats.py](../../dataset/genre_stats.py) — TMDb-genre catalog/report helpers.

### `candidates/`

Поиск и обслуживание кандидатов к просмотру.

- [candidates/service.py](../../candidates/service.py) — facade для UI.
- [candidates/models/](../../candidates/models/) — schema, keys, country/genre schema.
- [candidates/repositories/](../../candidates/repositories/) — SQLite-backed facade для load/save pool и criteria.
- [candidates/pool/](../../candidates/pool/) — dedupe, queries, stats, diagnostics, search helpers.
- [candidates/sources/tmdb/](../../candidates/sources/tmdb/) — TMDb Discover/Details build, scoring и import.
- [candidates/genres.py](../../candidates/genres.py) — runtime genre aliases для saved pool.

Инварианты pool:

- один общий pool; `criteria_name` в записи = `"pool"`;
- `pool_entry_key = normalized_title|year`;
- `title_identity_key = normalized_title|year`;
- stats показывают `unique_total` и физическое число записей в SQLite pool;
- read-path не удаляет watched;
- write-path очищает watched-кандидатов из pool;
- runtime-фильтры не пересобирают сохранённый pool;
- явная очистка дублей: `clean_common_pool_duplicates()` (console: Управление pool).

### `apis/`

Публичный runtime — только TMDb.

- [apis/tmdb_api.py](../../apis/tmdb_api.py) — TMDb Discover/Details.
- Legacy KP/IMDb helpers: [archive/legacy/apis/](../../archive/legacy/apis/).

### `storage/`

Низкоуровневое хранение и нормализация.

- [storage/data.py](../../storage/data.py) — dataset/meta: load/save/init, rename title.
- [storage/files.py](../../storage/files.py) — файлы, каталоги, SQLite backup/restore и legacy backup helpers.
- [storage/runtime.py](../../storage/runtime.py) — единая инициализация runtime-каталогов и SQLite schema.
- [storage/sqlite/](../../storage/sqlite/) — SQLite connection, migrations, repositories, diagnostics.
- [storage/legacy_json/](../../storage/legacy_json/) — explicit import/export compatibility для старых JSON layouts.
- [storage/normalize.py](../../storage/normalize.py) — нормализация `main_info`, `raw_scores`, legacy strip helpers.

### `config/`

Константы, схемы и справочники.

- [config/constant.py](../../config/constant.py) — пути и runtime-константы (`main_info` + TMDb `raw_scores`).
- [config/scheme.py](../../config/scheme.py) — схема полей watched payload.
- [candidates/models/genre_schema.py](../../candidates/models/genre_schema.py) — canonical genre keys для candidate pool.

### `posters/`

Poster-cache, загрузка и синхронизация постеров.

### `web/`

Read-only экспорт watched/add-title карточек.

### `scripts/`

Ручные entrypoints разложены по назначению; переиспользуемая логика должна жить
в активных слоях, а не в CLI-обёртках.

- `scripts/migrations/` — explicit migration/import/export utilities.
- `scripts/tmdb/` — TMDb build, refresh, backfill и network probes.
- `scripts/reports/` — builders сгенерированных отчётов и quality diagnostics.
- `scripts/screenshots/` — helpers локального захвата UI-скриншотов.
- `scripts/jobs/` — долгоживущие maintenance jobs.
- `scripts/duplicates/` — ручные инструменты инспекции дублей.

Правила output path: [REPORT_OUTPUT_POLICY.md](../operations/REPORT_OUTPUT_POLICY.md).

### `tests/`

Активный pytest-набор.

### `archive/legacy/`

Старый код, оставленный только для истории. Runtime его не импортирует.

## Основные сценарии

### Добавление watched-записи

1. UI принимает input title.
2. `dataset.resolve.service` делает TMDb search/details и готовит defaults.
3. UI показывает preview и принимает `user_score`.
4. `dataset.storage_movie.add_movie()` собирает payload.
5. `dataset.dataset_records.add_dataset_record()` сохраняет dataset/meta и запускает связанные side effects.

KP API и локальный IMDb dataset не участвуют в public add-title flow. IMDb rating/votes не используются; `imdb_id` может храниться только как external id из TMDb.

### Поиск кандидатов

1. Пользователь задаёт runtime-фильтр (defaults из SQLite criteria, запись `"pool"`).
2. `candidates.service` готовит view для UI.
3. `candidates.pool` и `candidates.repositories` читают общий pool; `app/core/filters` применяет runtime-фильтры.
4. Incomplete-кандидаты означают неполную TMDb/core metadata.

### TMDb candidate pool

1. UI выбирает страну, режим и Discover-фильтры.
2. `candidates.sources.tmdb.builder` получает TMDb Discover/Details.
3. TMDb-only normalizer/scoring готовит candidate contract.
4. Результат сохраняется в `data/exports/candidate_pool/`.
5. Saved result импортируется/мерджится в общий pool (auto-import или Управление pool).

### Перенос кандидата в watched

1. UI выбирает кандидата из pool.
2. `dataset.title_resolve.build_candidate_transfer_payload()` готовит defaults.
3. Пользователь подтверждает/редактирует форму.
4. `dataset.storage_movie.add_movie()` сохраняет запись.
5. `candidates.service.mark_candidate_watched_in_pool()` удаляет watched-кандидата из общего pool.

## Данные и артефакты

- `data/watchbane.sqlite3` — runtime source of truth: watched, meta, candidate pool, criteria, settings, user actions, poster metadata.
- Legacy JSON под `data/watched/`, `data/candidates/`, `data/settings.json`, `data/cache/posters/posters.json` — только explicit import/export compatibility.
- `data/exports/candidate_pool/*.json|*.csv` — сгенерированные результаты TMDb candidate pool.
- `data/diagnostics/*.json` — сгенерированные diagnostics.
- `data/cache/` — локальные кэши.
- `datasets/dataset_sql_light/imdb_light.sqlite3` — локальная SQL-база для non-candidate/internal сценариев.
- `screens/tmp_ui/` — локальные временные UI-скриншоты; содержимое ignored, tracked только `.gitkeep`.

Активные JSON в репозитории: нет runtime JSON-схем watched/genre; legacy paths — `scripts/migrations/legacy_paths.py`.

## Проверки

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
```
