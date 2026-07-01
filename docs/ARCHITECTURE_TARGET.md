# Целевая архитектура

Документ описывает архитектуру, к которой должен постепенно прийти `Watchbane`.

Проект должен стать чистым локальным поисковиком сериалов и тайтлов с личной watched-базой, candidate pool, внешним enrichment и удобным UI. Старые ML-эксперименты, временные JSON, diagnostics и ручные скрипты не должны определять активную структуру приложения.

## Главная Идея

`Watchbane` - это не ML-проект и не набор разрозненных скриптов. Целевая форма:

```text
локальная watched-база
        +
поиск новых сериалов через candidate pool
        +
enrichment из TMDb / IMDb SQL / KP
        +
console и desktop UI поверх стабильных сервисов
```

Источник правды хранится локально в `data/`, код работает через сервисные слои, UI не пишет JSON напрямую.

## Целевая Структура

```text
watchbane/
  start_console.py
  start_app.py

  app/                 # запуск и общая инициализация
  ui/
    console/           # консольные сценарии, меню, prompts
    gui/               # будущие общие GUI-компоненты, если понадобятся
  desktop/             # PyQt desktop-приложение

  dataset/             # watched-записи, meta, add/update/delete
  candidates/          # candidate pool, поиск, фильтры, dedupe
  posters/             # poster-cache и локальные постеры

  apis/                # TMDb, KP, IMDb SQL
  storage/             # load/save/init/backup низкого уровня
  config/              # схемы, константы, справочники
  common/              # чистые утилиты

  scripts/             # ручные utilities, миграции, diagnostics
  assets/
    desktop/           # desktop assets
  web/                 # read-only экспорт
  tests/               # активные pytest-тесты
  docs/                # документация
  archive/
    legacy/            # история, не runtime
```

Корень репозитория должен быть почти пустым: entrypoint-файлы, README/config tooling и папки верхнего уровня. Новые одиночные скрипты в корень не добавляются.

## Слои

Нижние слои не знают про верхние:

```text
common
  ↑
config
  ↑
storage
  ↑
apis        dataset        posters
  ↑           ↑              ↑
  └──── candidates ──────────┘
              ↑
      ui/console, desktop, web
              ↑
        start_console.py / start_app.py
```

Практически:

- `common` - функции без знания проекта и файлов.
- `config` - схемы, справочники, пути, константы.
- `storage` - чтение, запись, init, backup.
- `apis` - только получение внешних данных.
- `dataset` - watched-база и операции над ней.
- `candidates` - общий пул кандидатов и поиск по нему.
- `posters` - изображения и poster-cache.
- `ui/console` и `desktop` - пользовательские сценарии.
- `scripts` - ручные операции, не скрытый runtime.
- `archive/legacy` - не импортируется активным кодом.

## Правила Зависимостей

Разрешено:

```text
ui/console -> dataset, candidates, apis, storage, config, common
desktop    -> dataset, candidates, storage, config, common, posters
web        -> dataset, storage, config, common
candidates -> dataset, apis, storage, config, common
dataset    -> storage, apis, config, common, posters
posters    -> storage, apis, config, common
apis       -> config, common
storage    -> config, common
config     -> common, stdlib
common     -> stdlib
scripts    -> любой активный слой как ручной entrypoint
```

Запрещено:

- нижним слоям импортировать `ui`, `desktop` или `web`;
- `apis` писать в watched dataset или candidate pool;
- `candidates` напрямую вызывать `input()` / `print()` для бизнес-логики;
- UI напрямую сохранять JSON вместо вызова service-функций;
- активному runtime импортировать `archive/legacy`;
- возвращать зависимости от старой ML-модели;
- добавлять generated JSON в git без отдельного решения.

## Данные

Целевая структура локальных данных:

```text
data/
  watched/
    titles.json        # пользовательские записи
    meta.json          # enrichment/meta по watched-записям

  candidates/
    pool.json          # общий candidate pool
    criteria.json      # сохраненные критерии/дефолты
    watchlist.json     # позже: посмотреть
    hidden.json        # скрытые кандидаты

  cache/
    posters/
    tmdb/
    kp/

  exports/
    candidate_pool/
    edit_dataset.xlsx

  logs/
    api_requests.log

  backups/
```

В git остаются только справочники:

- `config/tags.json`;
- `config/genre_tags.json`;
- `apis/sql_title_aliases.json`.

Runtime JSON из `data/` не коммитятся. Их можно бэкапить, мигрировать и чистить отдельно от кода.

## Watched-База

Watched-запись хранится в `data/watched/titles.json`.

Минимальная модель:

```text
main_info:
  title
  user_score
  year
  country

raw_scores:
  kp_score
  kp_votes
  imdb_score
  imdb_votes
  kp_popularity
  imdb_popularity

tags_vibe:
  пользовательские vibe-теги

genre:
  has_* жанровые признаки
```

`data/watched/meta.json` хранит внешнее enrichment:

- `tmdb_id`;
- `imdb_id`;
- `kp_id`;
- description/overview;
- poster hints;
- source/raw metadata.

Правило: пользовательская watched-запись не должна зависеть от доступности API. API помогает заполнить данные, но не является источником правды.

## Candidate Pool

`data/candidates/pool.json` - общий пул потенциальных тайтлов.

Цель pool:

- хранить кандидатов между запусками;
- позволять фильтровать по стране, году, жанрам, рейтингам;
- не показывать уже просмотренное;
- поддерживать добор KP/IMDb/TMDb данных;
- переносить выбранного кандидата в watched через ручное подтверждение.

Инварианты:

- runtime-фильтр не пересобирает и не портит сохраненный pool;
- read-path не удаляет кандидатов;
- write-path после переноса в watched чистит watched-кандидата из pool;
- incomplete-кандидаты можно видеть отдельно и добирать через enrichment;
- dedupe централизован в `candidates`: `deduplicate_pool`, `dedupe_pool_by_similar_titles`, `clean_common_pool_duplicates`;
- UI показывает `unique_total`; при расхождении с JSON — предупреждение и пункт очистки дублей в console.

## Add / Update / Delete

Все изменения watched-базы проходят через service path:

```text
dataset.storage_movie.add_movie(...)
  -> dataset.dataset_records.add_dataset_record(...)

dataset.dataset_records.update_dataset_record(...)

dataset.delete_record.delete_watched_record(...)
```

UI отвечает за:

- ввод;
- preview;
- подтверждение;
- вывод результата.

Service отвечает за:

- валидацию;
- нормализацию;
- backup;
- запись dataset/meta;
- cleanup candidate pool;
- poster-cache side effects.

Storage отвечает только за:

- прочитать;
- записать;
- создать файл/папку;
- сделать backup.

## Внешние Источники

`apis/` не должен становиться доменной логикой.

TMDb, KP и IMDb SQL должны возвращать данные в предсказуемом формате, а решение “что с этим делать” принимают `dataset` или `candidates`.

Токены и локальные базы:

- `TMDB_TOKEN` не хранится в git;
- IMDb SQLite лежит локально в `datasets/dataset_sql_light/imdb_light.sqlite3`;
- API cache лежит в `data/cache/`.

## UI

Цель UI - быть тонким слоем сценариев.

Console:

- меню;
- prompts;
- подтверждения;
- вызов service-функций;
- человекочитаемый вывод.

Desktop:

- просмотр watched-базы;
- карточка тайтла;
- поиск и перенос кандидата;
- read-only аналитика;
- позже - удобное редактирование watched-записей.

UI не должен:

- знать формат всех JSON до мелочей;
- вручную чистить pool;
- обходить service layer;
- содержать тяжелую бизнес-логику.

## Scripts

`scripts/` - место для ручных операций:

- миграции старых данных;
- диагностика сети/API;
- одноразовые build/export utilities;
- отчеты для разработки.

Скрипт может импортировать активные слои, но приложение не должно зависеть от скрипта как от runtime-модуля.

Если скрипт становится нужным для обычного пользовательского сценария, его логика переносится в `dataset`, `candidates`, `storage` или `apis`, а в `scripts` остается только CLI-обертка.

## Archive

`archive/legacy/` - кладбище старого кода, но не мусорная корзина активного проекта.

Правила:

- активный код не импортирует `archive/legacy`;
- тесты из `archive/legacy` не входят в `pytest`;
- старую ML-модель не возвращаем в runtime;
- если из legacy нужна идея, переносим ее в активный слой явно и с тестами.

## Критерии Чистой Архитектуры

Проект считается близким к целевой структуре, когда:

- в корне нет случайных `.py`-скриптов, кроме entrypoints;
- runtime JSON лежат только в `data/` и игнорируются git;
- active tests проходят без старых external paths;
- UI не пишет JSON напрямую;
- candidate pool работает через `candidates.service`;
- watched mutations работают через `dataset`;
- `archive/legacy` не импортируется;
- новые функции добавляются в правильный слой, а не в самый удобный файл;
- `docs/PROJECT_MAP.md` совпадает с реальной структурой.

## Ближайшие Этапы

1. Дочистить runtime-артефакты в `data/exports/` и `data/diagnostics/`.
2. Укрепить границу `ui -> service -> storage`: убрать прямые записи из UI, если они еще остались.
3. Разделить крупные UI-сценарии в `ui/console/interface_funcs.py` на тематические модули.
4. Уточнить model/schema для watched title и candidate record.
5. Сделать единый слой миграций/инициализации данных.
6. Подтянуть desktop к тем же service-сценариям, что и console. **Частично:** watched CRUD и candidate search через `candidates.service` / `dataset.add_title_service`; pool operations и TMDb build остаются в console.
7. Обновлять этот документ после каждого крупного структурного шага.

## Проверки

Перед завершением структурного шага:

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
```

Для точечной правки можно запускать узкие тесты, но перед крупным коммитом нужен полный прогон.
