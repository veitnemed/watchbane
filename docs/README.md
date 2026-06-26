# Terminal Movies Learn

Консольный Python-проект для личной рекомендательной модели фильмов и сериалов.

Приложение хранит ваш dataset оценок, meta-данные и веса модели, умеет добавлять записи через локальную IMDb SQLite базу и внешние API, обучать линейную модель, а также собирать и обслуживать общий `candidate_pool` для будущего просмотра.

## Что умеет проект

- хранить `dataset`, `meta` и `weights` в JSON;
- добавлять записи через безопасный путь `dataset.storage_movie.add_movie() -> dataset.dataset_records.add_dataset_record()`;
- подтягивать defaults из IMDb SQL / KP / TMDb и показывать форму подтверждения перед сохранением;
- пересчитывать `computed_scores` из `raw_scores`;
- поддерживать vibe-теги и жанровую разметку;
- выгружать и загружать dataset через Excel;
- обучать линейную модель и считать `MAE`, `KP_MAE`, `LOO MAE`;
- хранить сохранённый `LOO MAE` в `config/model_metrics.json` и показывать его в главном меню;
- запускать read-only диагностику feature ablation для public-признаков и жанров;
- уточнять порядок личных оценок через попарное сравнение;
- создавать draft линейного распределения оценок без изменения dataset и применять его после LOO-preview;
- открывать desktop PyQt GUI для watched-базы с read-only карточкой тайтла, постером, метаданными, круговыми оценками и аналитикой;
- собирать старый общий candidate pool;
- собирать TMDb candidate pool v1 с ранними TMDb-фильтрами;
- импортировать TMDb result в общий пул;
- строить top prediction из общего пула по runtime-фильтрам;
- добирать KP для incomplete-кандидатов;
- переносить кандидатов из пула в dataset через форму ручного подтверждения.

## Запуск

Требуется Python 3.13+.

```powershell
py main.py
```

Для TMDb-потока нужен токен:

- переменная окружения `TMDB_TOKEN`;
- или `.env.local`;
- или `tmdb.env`.

Токен не должен попадать в git и в консольный вывод.

## Главное меню

1. `Данные`
2. `Обучение`
3. `Модель`
4. `Дополнительно`
5. `Пулл кандидатов`
6. `Выгрузить отчёт`

## Раздел `Данные`

- открыть Excel;
- загрузить Excel;
- добавить запись;
- показать мои оценки;
- данные о dataset;
- backup;
- переименовать запись;
- уточнить порядок оценок.

### Уточнение оценок

Пункт `Уточнить порядок оценок` запускает попарное сравнение записей с `user_score`. UI предлагает несколько сравнений, строит новый порядок и перед применением показывает preview изменений.

Перед применением всегда сохраняется snapshot в `config/rating_comparison_last_snapshot.json`. Если пользователь подтверждает изменения, оценки обновляются через `dataset.dataset_records.update_dataset_record(..., source_name="rating_comparison")`.

После `Показать мои оценки` доступно меню действий:

- `Линейное распределение оценок` - создаёт draft в `data/rating_order_drafts/rating_order_draft_YYYY-MM-DD_HH-MM-SS.json` и не меняет dataset;
- `Изменить оценку user_score` - обновляет одну оценку через safe update-service;
- `Изменить название` - запускает отдельный rename-flow;
- `Применить draft распределения оценок` - проверяет draft, считает LOO MAE до/после на копии dataset, создаёт backup и только после подтверждения применяет `proposed_score`.

Применение draft меняет только `main_info.user_score` в dataset. Веса и `config/model_metrics.json` не обновляются автоматически; после удачного применения нужно отдельно запустить LOO обучение.

## Раздел `Модель`

Текущее меню модели:

1. `Признаки`
2. `Тесты эффективности`
3. `Сделать прогноз`
0. `Главное меню`

### Feature ablation report

Пункт `Модель` -> `Тесты эффективности` -> `Диагностика признаков / feature ablation` показывает read-only диагностический отчёт по группам признаков.

Отчёт сравнивает:

- `Базовый IMDb` - прогноз равен raw `imdb_score`;
- `Базовый KP` - прогноз равен raw `kp_score`;
- `Модель только public` - `kp_score`, `kp_popularity`, `imdb_score`, `imdb_popularity`;
- `Модель только жанры` - жанровые `has_*`;
- `Public + жанры` - public-признаки вместе с жанрами.

Для model-вариантов каждый subset обучается со своим диагностическим `bias` и своей alpha, выбранной по LOO MAE. Эти веса печатаются в отчёте только для анализа и не сохраняются как рабочие веса модели.

После таблицы и блоков весов отчёт показывает `Топ-5 ошибок` для каждого варианта. Для baseline ошибок прогноз берётся напрямую из IMDb/KP рейтинга. Для model-вариантов ошибки и прогнозы берутся из LOO-fold: сериал временно убирается, subset-модель обучается на остальных записях, затем предсказывает убранный сериал.

Для каждого сериала в топе ошибок выводится `Топ-4 вклада` признаков. У baseline это вклад raw-рейтинга, у model-вариантов - самые большие по модулю вклады признаков из временной LOO-модели, которая дала этот прогноз.

Feature ablation report не должен:

- сохранять `weights.json`;
- сохранять `config/model_metrics.json`;
- менять dataset;
- менять candidate pool;
- запускать обычное обучение или LOO-обучение с сохранением.

## Раздел `Пулл кандидатов`

Текущее главное меню пула:

1. `Собрать новый пулл`
2. `Посмотреть пуллы кандидатов`
3. `Собрать топ из общего пула`
4. `Отметить просмотренные из пулла`
5. `Управление пуллами`
6. `Диагностика и обслуживание`
0. `Главное меню`

Пункт `Собрать новый пулл` сразу запускает основной TMDb-сценарий:

`TMDb -> IMDb SQL -> KP API`

Legacy-сборка через KP API оставлена отдельным пунктом в управлении пулами. Отдельного выбора между legacy/test-run режимами в основном пункте `Собрать новый пулл` нет.

### Подменю `Управление пуллами`

1. `Удалить пулл`
2. `Defaults фильтров top prediction`
3. `Импортировать TMDb result в общий пул`
4. `Собрать пулл через KP API (legacy)`
0. `Назад`

### Подменю `Диагностика и обслуживание`

1. `Показать подозрительные дубли`
2. `Добрать KP для неполных кандидатов`
3. `Показать вклады для кандидатов`
4. `Показать TMDb жанры по dataset`
0. `Назад`

## Общий candidate pool

Общий пул хранится в `C:/DATA/movies-learn/candidate_pool.json`.

Это runtime-пул из разных источников:

- legacy IMDb SQL -> KP API;
- TMDb result после импорта в общий пул.

Пул может содержать:

- разные `criteria_name`;
- разные `source`;
- разные страны;
- complete и incomplete кандидатов.

### Top prediction из общего пула

Перед расчётом топа пользователь выбирает runtime-фильтр по уже сохранённым кандидатам. `candidate_pool.json` при этом не меняется.

Поддерживаются фильтры:

- `criteria_name`;
- `source`;
- `country`;
- `year_min`, `year_max`;
- `include_genres`, `exclude_genres`;
- `min_kp_score`, `min_kp_votes`;
- `min_imdb_score`, `min_imdb_votes`;
- `min_tmdb_score`, `min_tmdb_votes`;
- `only_complete`.

После фильтрации UI показывает статистику:

- сколько кандидатов всего в pool;
- сколько осталось после выбранного фильтра;
- сколько готово к предикту;
- сколько incomplete пропущено.

Обычный top prediction не включает incomplete-кандидатов. Если incomplete есть, UI показывает их preview и подсказывает запустить пункт `Добрать KP для неполных кандидатов`.

## TMDb candidate pool v1

Основной flow:

1. TMDb Discover;
2. TMDb Details;
3. IMDb SQL enrichment;
4. KP enrichment;
5. сохранение отдельного JSON/CSV результата;
6. при необходимости импорт в общий пул.

Flow поддерживает:

- выбор страны;
- режим `quality` / `hidden_gems`;
- название пулла / `criteria_name` вручную или auto;
- ограничение страниц Discover;
- ограничение `details limit`;
- ранние TMDb-фильтры:
  - минимальный год;
  - максимальный год;
  - минимальный TMDb рейтинг;
  - минимум голосов TMDb.

В итоговой статистике TMDb flow печатает блок `TMDb Discover filters`.
`criteria_name` сохраняется в result JSON, settings-блок, каждый candidate и при импорте в общий candidate pool.

Диагностика `Показать TMDb жанры по dataset` сохраняет отчёт в `data/diagnostics/tmdb_genre_distribution_YYYY-MM-DD_HH-MM-SS.json` и не меняет dataset/candidate_pool.

## Добавление записи в dataset

Есть два основных сценария:

1. Ручное добавление из раздела `Данные`.
2. Перенос кандидата из `candidate_pool` через `Отметить просмотренные из пулла`.

В обоих случаях запись не добавляется молча. Сначала пользователь получает defaults, затем открывается форма подтверждения/ручного заполнения.

Форма позволяет:

- проверить `title` и `year`;
- выставить `user_score`;
- проверить и поправить `raw_scores`;
- подтвердить или поправить жанры;
- заполнить или изменить vibe-теги.

### Перенос кандидата из пула

При переносе кандидата:

- defaults строятся из данных кандидата;
- сохранение идёт через `dataset.storage_movie.add_movie() -> dataset.dataset_records.add_dataset_record()`;
- после успешного добавления кандидат удаляется из общего пула;
- для incomplete-кандидата показывается предупреждение, но ручной перенос разрешён.

Для TMDb-кандидата формата `tmdb_imdb_kp_v1` в defaults используются common-поля:

- `title`;
- `year`;
- `kp_score`;
- `kp_votes`;
- `imdb_score`;
- `imdb_votes`;
- `genres`;
- `description`;
- `tmdb_id`;
- `imdb_id`;
- `kp_id`;
- `source`.

В `meta` по возможности передаются:

- `tmdb_id`;
- `imdb_id`;
- `kp_id`;
- `description`;
- `source`.

## Структура dataset

Каждая запись содержит:

- `main_info`: `title`, `user_score`, `year`;
- `raw_scores`: `kp_score`, `kp_votes`, `imdb_score`, `imdb_votes`;
- `computed_scores`: вычисляемые числовые признаки;
- `tags_vibe`;
- `genre`.

## Ключевые файлы

- `main.py` - точка входа.
- `ui/console/` - текущее консольное меню, запросы, формы, UI-оркестрация.
- `ui/gui/` - место под будущий GUI.
- `desktop/` - текущий PyQt desktop GUI: watched-список, карточка тайтла, dialog оценки и read-only аналитика.
- `storage/` - низкоуровневое хранение (dataset/meta/weights, файлы, backup, нормализация).
- `dataset/` - записи, meta, Excel, статистика, теги, резолв тайтлов.
- `candidates/` - общий candidate pool и TMDb pipeline.
- `model/` - предикт, обучение, метрики, отчёты, feature ablation diagnostics.
- `apis/` - внешние API: KP (`kp_api`), TMDb (`tmdb_api`), IMDb SQL (`imdb_sql`).
- `common/` - чистые утилиты: валидация, формат-скоринг.
- `config/` - константы, схемы, каталоги тегов/жанров.
- `datasets/dataset_sql_light/imdb_light.sqlite3` - локальная IMDb SQLite база.
- `data/candidate_pool/` - TMDb JSON/CSV артефакты.
- `data/cache/tmdb/` - локальный кэш TMDb.

Архитектура слоёв и правила зависимостей: [ARCHITECTURE_TARGET.md](ARCHITECTURE_TARGET.md). Правила добавления функционала: [add_functions.md](add_functions.md). Визуальный контракт desktop GUI: [DESKTOP_STYLE_CONTRACT.md](DESKTOP_STYLE_CONTRACT.md). План переноса в desktop GUI: [DESKTOP_GUI_ROADMAP.md](DESKTOP_GUI_ROADMAP.md). Отчёты лежат в [reports/](reports/), последний отчёт по desktop-card polish: [DESKTOP_GUI_REPORT_2026-06-25.md](reports/DESKTOP_GUI_REPORT_2026-06-25.md).

## Полезные команды

Компиляция всех пакетов:

```powershell
py -m compileall common config storage dataset candidates model apis ui tests
```

Основной тестовый запуск:

```powershell
py tests\test.py
py -c "import tests.test_encoding as t; t.run_tests()"
```

Примеры CLI для TMDb candidate pool:

```powershell
python build_candidate_pool.py --country RU --pages 3 --details-limit 50 --mode quality
python build_candidate_pool.py --country KR --pages 3 --details-limit 50 --mode hidden_gems
```

## Где лежат данные

| Назначение | Путь |
| --- | --- |
| Dataset | `C:/DATA/movies-learn/dataset.json` |
| Weights | `C:/DATA/movies-learn/weights.json` |
| Criteria | `C:/DATA/movies-learn/candidate_criteria.json` |
| Общий candidate pool | `C:/DATA/movies-learn/candidate_pool.json` |
| Model metrics | `config/model_metrics.json` |
| Rating comparison snapshot | `config/rating_comparison_last_snapshot.json` |
| Rating order drafts | `data/rating_order_drafts/rating_order_draft_*.json` |
| API log | `C:/DATA/movies-learn/api_requests.log` |
| Meta | `C:/META/meta-movies-learn/meta_data.json` |
| Backup | `C:/BACKUP/movies-learn/BACKUP/` |
| Excel | `C:/TXT_FILES/movies-learn/edit_dataset.xlsx` |

## Что важно помнить

- `candidate_pool.json` не должен меняться от runtime-фильтра перед top prediction;
- обычный top prediction работает только по ready/complete-кандидатам;
- TMDb import и перенос кандидата в dataset - разные шаги;
- финальное сообщение об успешном добавлении печатает UI-слой, а не storage;
- переименование записи остаётся отдельной операцией и не должно идти через Excel patch или обычный update.
- rating comparison и draft распределения оценок меняют только `user_score` через `update_dataset_record()`;
- создание draft не меняет dataset, а применение draft не меняет веса и сохранённый `LOO MAE`.
- feature ablation report - диагностический read-only режим: он не сохраняет рабочие веса, `model_metrics.json`, dataset или candidate pool.
