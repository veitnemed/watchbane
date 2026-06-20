# Карта проекта

`Terminal Movies Learn` - консольная система для ведения личного dataset оценок и обучения простой рекомендательной модели.

Ниже карта проекта в текущем состоянии после рефакторинга слоёв. Целевая архитектура и правила зависимостей описаны в [docs/ARCHITECTURE_TARGET.md](/d:/VS%20PROJJJ/vscode%20projects/recommended/docs/ARCHITECTURE_TARGET.md:1), правила добавления нового функционала - в [add_functions.md](/d:/VS%20PROJJJ/vscode%20projects/recommended/add_functions.md:1).

## Быстрый вход

- [main.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/main.py:1) - вход в приложение.
- [README.md](/d:/VS%20PROJJJ/vscode%20projects/recommended/README.md:1) - пользовательское описание.
- [PROJECT_MAP.md](/d:/VS%20PROJJJ/vscode%20projects/recommended/PROJECT_MAP.md:1) - карта проекта.
- [add_functions.md](/d:/VS%20PROJJJ/vscode%20projects/recommended/add_functions.md:1) - правила добавления/изменения функционала.
- [ADD_RECORD_RULES.md](/d:/VS%20PROJJJ/vscode%20projects/recommended/ADD_RECORD_RULES.md:1) - контракт добавления и изменения записей.

## Слои и направление зависимостей

```
common  <-  config  <-  storage  <-  dataset / apis  <-  candidates / model  <-  ui
```

Нижние слои не знают о верхних. Запреты: `model` не импортирует `ui`; `dataset` не импортирует `ui`; `apis` не импортирует dataset/candidates/model/ui; `candidates` не вызывает `print()/input()`; `config`/`common` не зависят от верхних слоёв; UI не сохраняет данные и не вызывает API напрямую - только через сервисы.

## Основной runtime-поток

1. `main.py` инициализирует storage и регистрирует progress-reporter для candidates.
2. `ui.menu_state` собирает текущий state: dataset, weights, счётчики, ошибки модели.
3. `ui.ui` печатает меню.
4. `ui.global_menu` маршрутизирует пользователя по разделам.
5. `ui.interface_funcs` запускает конкретные сценарии UI.
6. `storage` / `dataset` / `candidates` выполняют работу с данными.
7. `apis` отдаёт внешние данные (KP, TMDb, IMDb SQL).
8. `model` строит признаки, считает предикт, ошибки и обучение.

## Папки и роли

### `common/`

Чистые утилиты без привязки к данным и меню.

- [common/valid.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/common/valid.py:1) - валидация ввода и payload.
- [common/format_score.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/common/format_score.py:1) - преобразование `raw_scores` в вычисляемые признаки.

### `config/`

Базовые константы, схемы и каталоги признаков.

- [config/constant.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/config/constant.py:1) - пути, названия секций, наборы признаков.
- [config/scheme.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/config/scheme.py:1) - схема `main_info`, `raw_scores`, `tags_vibe`, `genre`.
- [config/tags_work.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/config/tags_work.py:1) - чистое чтение/валидация каталога тегов `config/tags.json`.
- [config/tags.json](/d:/VS%20PROJJJ/vscode%20projects/recommended/config/tags.json:1) - vibe-теги.
- [config/genre_tags.json](/d:/VS%20PROJJJ/vscode%20projects/recommended/config/genre_tags.json:1) - жанровые признаки.
- [config/genre_tags.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/config/genre_tags.py:1) - нормализация и генерация `has_*` жанров.

### `storage/`

Низкоуровневое файловое хранилище. Знает, как сохранить файл, но не решает, зачем.

- [storage/data.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/storage/data.py:1) - dataset/meta/weights/metrics: load/save/init, rename title, LOO MAE.
- [storage/files.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/storage/files.py:1) - файлы, каталоги, backup, стартовая инициализация.
- [storage/normalize.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/storage/normalize.py:1) - нормализация `main_info`, `raw_scores`, `tags_vibe`, `genre`.

### `dataset/`

Пользовательский dataset: записи, meta, Excel, статистика, теги, резолв тайтлов.

- [dataset/dataset_records.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/dataset/dataset_records.py:1) - центральный add/update service.
- [dataset/storage_movie.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/dataset/storage_movie.py:1) - `add_movie()`, Excel row -> movie payload, пересчёт computed.
- [dataset/excel_work.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/dataset/excel_work.py:1) - Excel export/import.
- [dataset/dataset_stats.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/dataset/dataset_stats.py:1) - сводка dataset.
- [dataset/genre_import.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/dataset/genre_import.py:1) - массовая жанровая разметка.
- [dataset/genre_stats.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/dataset/genre_stats.py:1) - просмотр жанров dataset.
- [dataset/tags_work.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/dataset/tags_work.py:1) - мутации тегов в данных (`add_tag`, `delete_tag`, `delete_all_tags`, backup).
- [dataset/title_resolve.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/dataset/title_resolve.py:1) - сбор defaults из SQL/API/TMDb, payload переноса кандидата, сервисные обёртки над apis.

### `candidates/`

Пулы кандидатов к просмотру. Не вызывает `print()/input()` - прогресс отдаётся наверх через reporter.

- [candidates/candidate_pool.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/candidates/candidate_pool.py:1) - общий candidate pool: сбор, фильтры, ranking, retry KP, import/remove.
- [candidates/tmdb_candidate_pool.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/candidates/tmdb_candidate_pool.py:1) - TMDb candidate pool v1; `set_progress_reporter()`, `build_summary_lines()`.

### `apis/`

Внешние источники данных. Только получают данные и возвращают результат наверх.

- [apis/kp_api.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/apis/kp_api.py:1) - KP/внешний API для рейтингов, описаний и candidate-поиска.
- [apis/tmdb_api.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/apis/tmdb_api.py:1) - TMDb Discover, Details и нормализация ответов.
- [apis/imdb_sql.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/apis/imdb_sql.py:1) - поиск в локальной IMDb SQLite базе.

### `model/`

Модель и обучение. Не импортирует `ui`.

- [model/model.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/model/model.py:1) - предикт, MAE, feature logic, `reset_weights()`, save-if-improved.
- [model/linear_regression_train.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/model/linear_regression_train.py:1) - линейное обучение, LOO, метрики, отчёты.
- [model/train_report.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/model/train_report.py:1) - отчёт по модели.
- [model/noise_experiment.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/model/noise_experiment.py:1) - шумовая устойчивость (чистая логика).

### `ui/`

Консольный UI и маршрутизация. Спрашивает пользователя и показывает результат, работу делают нижние слои.

- [ui/ui.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/ui.py:1) - печать экранов и меню.
- [ui/global_menu.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/global_menu.py:1) - циклы меню и переходы между разделами.
- [ui/interface_funcs.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/interface_funcs.py:1) - UI-оркестрация сценариев.
- [ui/request.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/request.py:1) - формы, prompts, сбор `movie_request`.
- [ui/title_presenters.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/title_presenters.py:1) - карточки SQL/API/defaults.
- [ui/candidate_pool_ui.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/candidate_pool_ui.py:1) - интерактивная работа с criteria.
- [ui/tags_menu.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/tags_menu.py:1) - управление vibe-тегами.
- [ui/backup_menu.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/backup_menu.py:1) - backup и restore.
- [ui/train_menu.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/train_menu.py:1) - интерактивные режимы обучения и шумовой эксперимент.
- [ui/rating_comparison.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/rating_comparison.py:1) - попарное сравнение оценок.
- [ui/menu_state.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/ui/menu_state.py:1) - сбор состояния меню.

### `tests/`

Тесты проекта. Точка входа - [tests/test.py](/d:/VS%20PROJJJ/vscode%20projects/recommended/tests/test.py:1).

## Текущее меню

### Главное меню

1. `Данные`
2. `Обучение`
3. `Модель`
4. `Дополнительно`
5. `Пулл кандидатов`
6. `Выгрузить отчёт`

### `Пулл кандидатов`

Главный экран:

1. `Собрать новый пулл`
2. `Посмотреть пуллы кандидатов`
3. `Собрать топ из общего пула`
4. `Отметить просмотренные из пулла`
5. `Управление пуллами`
6. `Диагностика и обслуживание`
0. `Главное меню`

Подменю `Собрать новый пулл`:

- `TMDb -> IMDb SQL -> KP API`
- `Legacy IMDb SQL -> KP API`
- `TMDb test-run`

Подменю `Управление пуллами`:

- `Удалить пулл`
- `Фильтрация / редактирование критериев`
- `Импортировать TMDb result в общий пул`

Подменю `Диагностика и обслуживание`:

- `Показать подозрительные дубли`
- `Добрать KP для неполных кандидатов`
- `Показать вклады для кандидатов`

## Ключевые потоки

### 1. Ручное добавление записи

1. `ui.interface_funcs.request_object()`
2. `ui.request.request_api_defaults(confirm_genres=True)`
3. `dataset.title_resolve.resolve_title_for_training()`
4. `ui.request.request_all_scores(defaults)`
5. `dataset.storage_movie.add_movie(print_message=False)`
6. `dataset.dataset_records.add_dataset_record()`

UI печатает финальное сообщение сам. Service возвращает `AddRecordResult`.

### 2. Перенос кандидата из пула в dataset

1. `ui.interface_funcs.mark_candidate_as_watched()`
2. выбор `criteria_name` и кандидата;
3. `dataset.title_resolve.build_candidate_transfer_payload(candidate)`;
4. предупреждение для incomplete-кандидата, если нужно;
5. `ui.request.request_all_scores(defaults)`;
6. `dataset.storage_movie.add_movie(meta_payload=..., pool_candidate=..., print_message=False)`;
7. `add_dataset_record()` сохраняет запись;
8. после успеха связанный кандидат удаляется из общего пула.

### 3. Top prediction из общего пула

1. `ui.interface_funcs.show_global_candidate_top()`
2. загрузка всех кандидатов;
3. runtime-фильтр через `candidate_pool.filter_saved_candidates_for_prediction()`;
4. ready-filter через `candidate_pool.is_candidate_ready_for_prediction()`;
5. ranking через `candidate_pool.rank_candidates_by_predict()`.

### 4. Retry KP для incomplete-кандидатов

1. `ui.interface_funcs.retry_kp_for_incomplete_candidates()`
2. выбор scope: все или конкретный `criteria_name`;
3. preview и подтверждение перед API-запросами;
4. запуск `candidates.candidate_pool.retry_kp_enrichment_for_pool(...)`.

### 5. TMDb candidate pool v1

1. `ui.interface_funcs.run_tmdb_candidate_pool_flow()`
2. выбор страны, режима и обычного запуска или test-run;
3. ввод ранних Discover-фильтров (`year_min`, `year_max`, `min_tmdb_score`, `min_tmdb_votes`);
4. `candidates.tmdb_candidate_pool.build_candidate_pool(...)`;
5. прогресс отдаётся через `set_progress_reporter` (печатает UI), итог - `build_summary_lines`;
6. сохранение отдельного TMDb result; при необходимости импорт в общий пул.

### 6. Обучение модели

- линейные режимы и шумовой эксперимент: `ui.train_menu.train_linear_model()`, `ui.train_menu.run_noise_sensitivity()` (UI-обёртки над `model.linear_regression_train` и `model.noise_experiment`);
- LOO-обучение: `model.linear_regression_train.run_loo_training()`;
- сброс весов: `ui.interface_funcs.reset_weights_model()` -> `model.reset_weights()`.

## Где менять поведение

- меню и маршрутизацию: `ui/ui.py`, `ui/global_menu.py`
- prompts и UI-сценарии: `ui/interface_funcs.py`, `ui/request.py`, `ui/train_menu.py`
- правила сохранения записи: `dataset/storage_movie.py`, `dataset/dataset_records.py`
- defaults и перенос кандидата: `dataset/title_resolve.py`
- общий candidate pool: `candidates/candidate_pool.py`
- TMDb pipeline: `apis/tmdb_api.py`, `candidates/tmdb_candidate_pool.py`
- SQL-поиск: `apis/imdb_sql.py`
- обучение и предикт: `model/model.py`, `model/linear_regression_train.py`
- низкоуровневое сохранение: `storage/data.py`, `storage/files.py`

## Данные и артефакты

- `C:/DATA/movies-learn/dataset.json` - dataset.
- `C:/META/meta-movies-learn/meta_data.json` - meta.
- `C:/DATA/movies-learn/weights.json` - веса модели.
- `C:/DATA/movies-learn/candidate_pool.json` - общий candidate pool.
- `data/candidate_pool/*.json|*.csv` - TMDb candidate pool result.
- `data/cache/tmdb/` - локальный кэш TMDb Discover/Details.
- `datasets/dataset_sql_light/imdb_light.sqlite3` - локальная IMDb SQLite база.

## Проверки

```powershell
py -m compileall common config storage dataset candidates model apis ui tests
py tests\test.py
py main.py
```

Для меню `candidate_pool` полезно отдельно проверять: возврат по `0` из каждого подменю, legacy flow, TMDb flow, import TMDb result, top prediction с runtime-фильтрами, retry KP с preview, перенос кандидата в dataset через форму.
