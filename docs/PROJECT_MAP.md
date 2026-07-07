# Карта проекта

`Watchbane` - локальный Python-проект для ведения watched-базы и поиска сериалов/тайтлов через TMDb-only candidate pool.

Старая ML-модель перенесена в `archive/legacy/model/` и не является активной частью runtime.

## Быстрый вход

- [README.md](README.md) - пользовательское описание проекта.
- [LOGICAL_ARCHITECTURE.md](LOGICAL_ARCHITECTURE.md) - логические зоны проекта без физического переноса файлов.
- [STRUCTURE_PLAN.md](STRUCTURE_PLAN.md) - план структурной чистки.
- [REFACTORING_CHECKLIST.md](REFACTORING_CHECKLIST.md) - чеклист безопасного завершения рефакторинга.
- [DATA_STORAGE_PLAN.md](DATA_STORAGE_PLAN.md) - структура локального хранения данных.
- [WORKSPACE_HOUSEKEEPING.md](WORKSPACE_HOUSEKEEPING.md) - правила для временных скриншотов, локальных кэшей и больших generated-артефактов.
- [add_functions.md](add_functions.md) - правила добавления и изменения функционала.
- [ADD_RECORD_RULES.md](ADD_RECORD_RULES.md) - контракт добавления и изменения записей.
- [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md) - визуальный контракт desktop GUI.
- [DESKTOP_MODULE_MAP.md](DESKTOP_MODULE_MAP.md) - карта модулей desktop и правила расширения.
- [DESKTOP_GUI_ROADMAP.md](DESKTOP_GUI_ROADMAP.md) - roadmap desktop GUI.
- [TMDB_ONLY_CANDIDATE_FLOW.md](TMDB_ONLY_CANDIDATE_FLOW.md) - TMDb-only candidate contract, migration, refresh and scoring.

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
- `candidates` не вызывает `input()` и `print()`, прогресс отдает наверх;
- UI не пишет JSON напрямую, а вызывает сервисы.

## Runtime-поток

1. `start_console.py` или `start_app.py` запускает приложение.
2. `storage` инициализирует базовые файлы и каталоги.
3. `ui.console` или `desktop` собирает пользовательский сценарий.
4. `dataset` работает с watched-записями, meta, жанрами, тегами и Excel.
5. `candidates` строит и фильтрует candidate pool.
6. `apis` отдает данные внешних и локальных источников для сервисов.
7. `posters` синхронизирует poster-cache и локальные изображения.

## Папки

### `app/`

Входные сценарии приложения и общая инициализация.

### `desktop/`

PyQt desktop GUI для watched-базы, карточки тайтла, поиска и аналитики.

Структура пакетов: [DESKTOP_MODULE_MAP.md](DESKTOP_MODULE_MAP.md).

- [desktop/app.py](../desktop/app.py) - главное окно (shell, вкладки).
- [desktop/watched/](../desktop/watched/) - watched feature (`model`, `tab`, dialogs).
- [desktop/shared/detail/](../desktop/shared/detail/) - detail card widget.
- [desktop/candidates/](../desktop/candidates/) - candidate search (`session`, `filters_view`, `list_view`, `presenters`).
- [desktop/analytics/](../desktop/analytics/) - read-only Information tab: genre reports and chart constructor (`view`, `chart_constructor`, `charts`).
- [desktop/shared/widgets/](../desktop/shared/widgets/) - переиспользуемые виджеты (sliders, search, chips).
- [desktop/theme/](../desktop/theme/) - tokens и QSS builders (`tokens.py`, `styles/`).

### `ui/console/`

Консольный интерфейс, меню, prompts и сценарии пользователя.

- [ui/console/console_app.py](../ui/console/console_app.py) - запуск console UI.
- [ui/console/ui.py](../ui/console/ui.py) - отрисовка меню.
- [ui/console/global_menu.py](../ui/console/global_menu.py) - тонкая маршрутизация top-level разделов.
- [ui/console/maintenance_menu.py](../ui/console/maintenance_menu.py) - главный maintenance hub: состояние, backup, metadata/cache, diagnostics.
- [ui/console/watched_menu.py](../ui/console/watched_menu.py) - просмотренное: show/rename/delete/Excel/add.
- [ui/console/pool_menu.py](../ui/console/pool_menu.py) - candidate pool: view/search/mark watched, cleanup, import/build.
- [ui/console/search_hub_menu.py](../ui/console/search_hub_menu.py) - read-only поиск и инспекция.
- [ui/console/reference_menu.py](../ui/console/reference_menu.py) - справочники, жанры и теги.
- [ui/console/interface_funcs.py](../ui/console/interface_funcs.py) - compatibility facade и оставшиеся watched-сценарии.
- [ui/console/api_tools.py](../ui/console/api_tools.py) - диагностика внешних API.
- [ui/console/sql_tools.py](../ui/console/sql_tools.py) - internal legacy helper для локальной SQL-базы, не публичный candidate-путь.
- [ui/console/poster_tools.py](../ui/console/poster_tools.py) - обслуживание watched metadata и poster-cache.
- [ui/console/candidate_pool_tools.py](../ui/console/candidate_pool_tools.py) - обслуживание и диагностика общего candidate pool.
- [ui/console/tmdb_pool_tools.py](../ui/console/tmdb_pool_tools.py) - TMDb build/import flow для candidate pool.
- [ui/console/request.py](../ui/console/request.py) - формы и prompts.
- [ui/console/search_menu.py](../ui/console/search_menu.py) - поиск по candidate pool.
- [ui/console/candidate_pool_ui.py](../ui/console/candidate_pool_ui.py) - настройки сбора и defaults общего pool.
- [ui/console/tags_menu.py](../ui/console/tags_menu.py) - управление vibe-тегами.
- [ui/console/backup_menu.py](../ui/console/backup_menu.py) - backup и restore.

### `dataset/`

Watched dataset: добавление, обновление, удаление, meta, Excel, статистика, жанры и теги.

- [dataset/dataset_records.py](../dataset/dataset_records.py) - центральный add/update service.
- [dataset/storage_movie.py](../dataset/storage_movie.py) - сбор payload и сохранение записи.
- [dataset/delete_record.py](../dataset/delete_record.py) - безопасное удаление watched-записи.
- [dataset/title_resolve.py](../dataset/title_resolve.py) - thin facade для TMDb-only add-title и переноса кандидата.
- [dataset/dataset_stats.py](../dataset/dataset_stats.py) - сводка dataset.
- [dataset/genre_stats.py](../dataset/genre_stats.py) - просмотр жанров.
- [dataset/tags_work.py](../dataset/tags_work.py) - мутации тегов.

### `candidates/`

Поиск и обслуживание кандидатов к просмотру.

- [candidates/service.py](../candidates/service.py) - facade для UI.
- [candidates/models/](../candidates/models/) - schema, keys, country/genre schema.
- [candidates/repositories/](../candidates/repositories/) - load/save pool и criteria JSON.
- [candidates/pool/](../candidates/pool/) - dedupe, queries, stats, diagnostics, search helpers.
- [candidates/sources/tmdb/](../candidates/sources/tmdb/) - TMDb Discover/Details build, scoring и import.
- [candidates/genres.py](../candidates/genres.py) - runtime genre aliases для saved pool.

Инварианты pool:

- один общий pool; `criteria_name` в записи = `"pool"`;
- `pool_entry_key = normalized_title|year`;
- `title_identity_key = normalized_title|year`;
- stats показывают `unique_total` и, при наличии, лишние записи в JSON;
- read-path не удаляет watched;
- write-path очищает watched-кандидатов из pool;
- runtime-фильтры не пересобирают сохраненный pool;
- явная очистка дублей: `clean_common_pool_duplicates()` (console: Управление pool).

### `apis/`

Внешние источники данных.

- [apis/kp_api.py](../apis/kp_api.py) - internal/non-candidate external API helper, не часть public candidate flow.
- [apis/tmdb_api.py](../apis/tmdb_api.py) - TMDb Discover/Details.
- [apis/imdb_sql.py](../apis/imdb_sql.py) - internal/non-candidate local SQL helper, не часть public candidate flow.
- [apis/sql_title_aliases.json](../apis/sql_title_aliases.json) - alias-справочник для SQL-поиска.

### `storage/`

Низкоуровневое хранение и нормализация.

- [storage/data.py](../storage/data.py) - dataset/meta: load/save/init, rename title.
- [storage/files.py](../storage/files.py) - файлы, каталоги, backup.
- [storage/runtime.py](../storage/runtime.py) - единая инициализация runtime-каталогов и JSON.
- [storage/normalize.py](../storage/normalize.py) - нормализация `main_info`, `raw_scores`, `tags_vibe`, `genre`.

### `config/`

Константы, схемы и справочники.

- [config/constant.py](../config/constant.py) - пути и runtime-константы.
- [config/scheme.py](../config/scheme.py) - схема полей.
- [config/tags.json](../config/tags.json) - vibe-теги.
- [config/genre_tags.json](../config/genre_tags.json) - жанровые признаки.
- [config/tags_work.py](../config/tags_work.py) - чтение/валидация тегов.
- [config/genre_tags.py](../config/genre_tags.py) - чтение/валидация жанров.

### `posters/`

Poster-cache, загрузка и синхронизация постеров.

### `web/`

Read-only экспорт watched/add-title карточек.

### `scripts/`

Ручные diagnostic/build utilities.

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

1. Пользователь задает runtime-фильтр (defaults из `criteria.json`, запись `"pool"`).
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

- `data/watched/titles.json` - watched dataset.
- `data/watched/meta.json` - meta/enrichment.
- `data/candidates/pool.json` - общий candidate pool.
- `data/candidates/criteria.json` - defaults сбора и search-фильтров (запись `"pool"`).
- `data/exports/candidate_pool/*.json|*.csv` - generated TMDb candidate pool results.
- `data/diagnostics/*.json` - generated diagnostics.
- `data/cache/` - локальные кэши.
- `datasets/dataset_sql_light/imdb_light.sqlite3` - локальная SQL-база для non-candidate/internal сценариев.
- `screens/tmp_ui/` - локальные временные UI-скриншоты; содержимое ignored, tracked только `.gitkeep`.

Активные JSON в репозитории:

- `config/tags.json`;
- `config/genre_tags.json`;
- `apis/sql_title_aliases.json`.

## Проверки

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
```
