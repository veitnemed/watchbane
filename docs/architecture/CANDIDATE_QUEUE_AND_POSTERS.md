# Candidate Queue And Posters

## Current runtime guarantees (July 2026)

- Opening Watchbane does not immediately replenish or rebuild the persisted candidate pool.
- The first transition from an empty deck to a populated onboarding deck always starts the poster preparation gate.
- The visible deck waits up to eight seconds for the active poster batch while showing deterministic progress; cached batches normally pass immediately.
- Poster resolution prefers the selected data language, then reuses any valid cached poster from the root record or another locale before making a network request.
- A localized poster URL that is not cached no longer hides an already cached poster for the same title.
- Candidate poster downloads remain bounded to four concurrent requests and never execute on the UI thread.
- A failed CDN request leaves a stable placeholder and an explicit unavailable status; it does not block navigation or mutate recommendation ranking.

These guarantees are covered by startup, deck reveal, presenter fallback and poster-prefetch regression tests.

Этот документ описывает текущий runtime-путь вкладок **Фильтры** и **Кандидаты**: от сохраненного `candidate pool` до видимой очереди рекомендаций, а также отдельный путь подгрузки постеров.

## Короткая схема

1. `candidate pool` хранится локально в SQLite и читается через `candidates.service`.
2. Вкладка **Фильтры** сохраняет направление поиска и применяет локальные фильтры к уже сохраненному пулу.
3. Если локально подходящих кандидатов мало, вкладка **Фильтры** запускает фоновый добор из TMDb.
4. Вкладка **Кандидаты** строит локальную колоду рекомендаций из текущего пула.
5. Колода состоит из активной очереди и резерва.
6. Постеры не блокируют построение самой колоды: они догружаются отдельной ограниченной очередью.

## Основные компоненты

| Зона | Компонент | Роль |
| --- | --- | --- |
| Чтение пула | `candidates.service.get_search_overview_view()` | Возвращает сохраненные кандидаты и статистику пула. |
| Фильтры GUI | `desktop.candidates.filters_view.CandidateFiltersView` | Собирает настройки поиска, применяет локальные фильтры и запускает TMDb-добор при нехватке кандидатов. |
| Сессия GUI | `desktop.candidates.session.CandidateSearchSession` | Хранит текущие фильтры, результат локального поиска, сортировку и вектор рекомендаций. |
| Фоновый поиск | `desktop.candidates.workers.search_worker.CandidateSearchWorker` | Фильтрует и сортирует pool без блокировки UI. |
| Добор TMDb | `desktop.candidates.workers.filter_replenish_worker.FilterReplenishWorker` | Запускает сетевой добор кандидатов из TMDb в отдельном потоке. |
| Колода | `candidates.recommendation_deck_service.RecommendationDeckService` | Строит активную очередь и резерв из локального пула. |
| Вкладка кандидатов | `desktop.candidates.list_view.CandidateListView` | Показывает колоду, запускает подготовку постеров, обрабатывает действия пользователя. |
| Постеры | `desktop.candidates.poster_prefetch.CandidatePosterPrefetchController` | Качает preview-постеры через Qt network, батчами и без блокировки UI. |
| Poster hints | `posters.cache.extract_existing_poster_info()` | Выбирает лучший доступный `poster_url` или `poster_path` из записи кандидата. |

## Локальный путь: как строится очередь кандидатов

### 1. Загрузка сохраненного пула

Вкладка **Кандидаты** не ходит в TMDb сама по себе. Она строит очередь из уже сохраненного локального `candidate pool`.

Путь чтения:

```text
CandidateListView
  -> CandidateSearchSession.overview()
  -> candidates.service.get_search_overview_view()
  -> candidates.service.get_pool_view()
  -> candidates.pool.queries.get_all_candidates()
  -> SQLite candidate_records / payload_json
```

`CandidateListView._load_pool_for_deck()` берет кандидатов из текущего `session.overview()` и передает их в `RecommendationDeckService` как словарь по `candidate_detail_identity`.

### 2. Применение фильтров

Вкладка **Фильтры** собирает `CandidateDiscoveryPreferences`:

- направление / пресет;
- тип контента;
- режим анимации;
- период выхода;
- страны;
- включенные и исключенные жанры;
- годовой диапазон;
- минимальный TMDb score;
- минимальные TMDb votes;
- `only_complete`;
- `only_unwatched`;
- `hide_hidden`.

После нажатия кнопки применения:

```text
CandidateFiltersView._apply_filters()
  -> save_discovery_preferences(...)
  -> preferences.to_candidate_filters(DEFAULT_BROWSE_FILTERS)
  -> CandidateSearchSession.apply_filters_async(...)
  -> CandidateSearchWorker
  -> service.search_candidate_pool(...)
  -> service.sort_search_candidates(...)
```

Это локальная операция. Она не должна создавать новые кандидаты и не должна менять сам pool.

### 3. Построение recommendation deck

Когда вкладка **Кандидаты** активируется, загрузка колоды планируется через короткий таймер, чтобы не блокировать первичный показ окна:

```text
CandidateListView.on_tab_activated()
  -> _deck_load_timer.start(25)
  -> _load_recommendation_deck(force_new=False)
  -> RecommendationDeckService.refresh_deck(...)
```

`refresh_deck()` использует cache key:

- текущий день;
- фильтры кандидатов;
- `recommendation_vector`;
- `variation_seed`.

Если cache key не поменялся и `force_new=False`, возвращается уже построенная колода. Если пользователь нажал новую колоду или поменял условия, строится новая.

### 4. Отбор eligible-кандидатов

`RecommendationDeckService.build_deck()` сначала отсекает кандидатов, которые не должны попадать в рекомендации.

Кандидат исключается, если:

- уже есть в watched dataset;
- уже добавлен в watchlist;
- скрыт пользователем;
- год релиза больше текущего года;
- не проходит viability-gate для тайтлов без надежного рейтинга;
- не проходит текущие фильтры;
- является дублем уже выбранного кандидата;
- был недавно показан в рекомендациях.

Недавно показанные кандидаты не удаляются навсегда. Они складываются в fallback-список и могут быть использованы, если нормальных eligible-кандидатов вообще не осталось.

### 5. Ранжирование

Ранжирование локальное и детерминированное на день. Случайность заменена стабильным hash seed:

```text
day + variation_seed + candidate identity
```

На порядок влияют:

- соответствие настроению из `RecommendationVector`;
- персональные fit-поля, если они есть в кандидате;
- базовый score кандидата;
- hidden-gem score;
- TMDb popularity;
- уровень редкости;
- уровень разнообразия;
- стабильный hash для перемешивания равных кандидатов.

Если настроение задано явно, кандидаты делятся на tiers:

| Tier | Что означает |
| --- | --- |
| A | точное попадание в настроение |
| B | близкий жанровый сосед |
| C | допустимое исследовательское отклонение |
| D | конфликтный жанровый профиль |

`openness_level` определяет, сколько кандидатов из исследовательской зоны C можно добавить к близким A/B.

`diversity_level` влияет на то, насколько активно очередь разбавляется по:

- media type;
- первому жанру;
- стране;
- десятилетию.

### 6. Активная очередь и резерв

Текущие размеры:

| Параметр | Значение |
| --- | --- |
| Активная очередь | 25 кандидатов |
| Резерв | 70 кандидатов |
| Порог добора резерва | 40 кандидатов |
| Обычный лимит тайтлов без рейтинга | 6 |
| Расширенный лимит тайтлов без рейтинга | 12, если выбран новый контент и явная страна |

Колода выглядит так:

```text
deck = {
  active: [...25],
  reserve: [...70],
  refill_needed: bool,
  underfilled_reason: str | None,
  excluded: counters,
  relevance_counts: counters
}
```

В UI показывается только `active`. `reserve` нужен для быстрой замены карточек после действий пользователя.

### 7. Что происходит после действия с кандидатом

Когда пользователь отмечает кандидата как просмотренный, добавляет в список или скрывает:

```text
CandidateListView._apply_recommendation_action(...)
  -> RecommendationDeckService.apply_action_and_refill(...)
```

Дальше:

1. состояние кандидата записывается в watched/watchlist/hidden;
2. кандидат удаляется из `active` и `reserve`;
3. из `reserve` подбирается замена;
4. если резерва мало, вызывается локальный `top_up_deck()`;
5. если локально кандидатов все еще мало, UI может запросить TMDb-добор через вкладку **Фильтры**.

Для явного настроения replacement старается сохранить близкий tier. Без явного настроения он подбирает замену с похожим base score.

## Когда запускается TMDb-добор

TMDb-добор запускается не при каждом открытии вкладки **Кандидаты**. Он привязан к явному применению discovery-настроек и к нехватке локальных кандидатов.

Перед запуском добора `CandidateFiltersView._discovery_pool_needs_replenish()` считает, сколько локальных кандидатов подходит под текущие discovery-фильтры и recommendation vector.

Порог:

```text
DEFAULT_ACTIVE_LIMIT + DEFAULT_REFILL_THRESHOLD
= 25 + 40
= 65
```

Если подходящих локальных кандидатов меньше 65, создается pending replenish intent. Сначала все равно применяется локальный поиск, чтобы пользователь сразу увидел то, что уже есть. После завершения локального поиска стартует `FilterReplenishWorker`.

### Ограничения одного добора

| Параметр | Значение |
| --- | --- |
| Максимум новых кандидатов за один запуск | 30 |
| Максимум страниц TMDb на bucket | 3 |
| Максимум details-запросов | до 60 |

### Как строится TMDb-план

`FilterReplenishIntent` превращается в plan:

```text
countries x media_type -> buckets
```

Например, если выбраны две страны и `media_type=both`, получится до четырех bucket:

```text
RU:movie
RU:tv
US:movie
US:tv
```

Квота `target_add_count` распределяется между bucket. Для каждого bucket строятся TMDb Discover параметры:

- media type;
- country / origin country;
- годы;
- include genres;
- exclude genres;
- animation mode;
- score/votes ограничения, если они заданы.

### Как принимаются новые кандидаты

Каждый raw-result из TMDb Discover проходит цепочку:

1. собрать базовый candidate из discover result;
2. проверить наличие `tmdb_id`;
3. проверить наличие title;
4. проверить год;
5. отсеять watched;
6. отсеять hidden;
7. отсеять уже существующий candidate pool;
8. отсеять дубли внутри текущего добора;
9. запросить TMDb Details, если доступен details-клиент;
10. нормализовать genres, localized-блоки, poster fields и detail fields;
11. пересчитать completeness/quality/hidden/final scores;
12. проверить quality-gate;
13. добавить в selected.

После успешного добора кандидаты импортируются в общий pool:

```text
candidates.sources.tmdb.importer.import_tmdb_candidates_to_common_pool(...)
```

Importer:

- нормализует запись для storage;
- убирает старые KP/IMDb rating fields;
- не импортирует watched-кандидатов;
- ищет существующую запись по TMDb identity и storage identity;
- добавляет новую запись или обновляет старую, если новая качественнее;
- сохраняет общий pool.

После сохранения GUI делает:

```text
reload_filter_options()
CandidateSearchSession.reload_from_pool(force=True)
```

То есть список и колода начинают видеть новые записи без перезапуска приложения.

## Как подгружаются постеры

Постеры имеют отдельный путь. Кандидат может быть в очереди и показываться даже без готового локального файла постера.

### 1. Выбор poster metadata

Для кандидата сначала строятся poster hints:

```text
desktop.candidates.presenters._candidate_poster_hints()
  -> dataset.resolve.poster_hints.build_poster_hints_from_candidate()
  -> posters.cache.extract_existing_poster_info()
```

`extract_existing_poster_info()` ищет постер в таком порядке:

1. `localized.<data_language>.poster_url`;
2. `localized.<data_language>.poster_path`;
3. root-поля `poster_url`, `preview_url`, `tmdb_poster_url`, `cover_url`, `image_url` и похожие;
4. root-поля `poster_path`, `tmdb_poster_path`;
5. вложенный `poster.url`;
6. вложенный `poster.path`;
7. `cover` или `image`, если это HTTP URL;
8. fallback на другой localized-язык, если в запрошенном языке постера нет.

Если найден только `poster_path`, из него строится TMDb URL:

```text
https://image.tmdb.org/t/p/w342/<poster_path>
```

Это значит: если RU-постера нет, но в записи есть EN или другой локализованный постер, система может взять его как fallback.

### 2. Проверка локального файла

Перед сетью UI проверяет, есть ли уже локальный файл:

```text
resolve_local_poster_path_for_candidate(...)
  -> desktop.shared.detail.posters.resolve_local_poster_path_from_record(...)
```

Порядок:

1. локальный `poster_path` из display card;
2. локальный `poster_src` из display card;
3. локальный `poster_path` из записи;
4. локальный `poster_src` из записи;
5. локальный `poster.path`;
6. локальный `poster.poster_path`;
7. preview-cache по `poster_url`;
8. watched poster cache по title/year, если URL не конфликтует.

Если локальный файл найден, сеть не используется.

### 3. Batch-подготовка постеров перед раскрытием колоды

Когда строится новая replacement-колода, вкладка **Кандидаты** показывает экран подготовки и запускает batch:

```text
CandidateListView._present_recommendation_deck(..., prepare_posters=True)
  -> CandidatePosterPrefetchController.start_batch(active_candidates)
```

Текущие параметры:

| Параметр | Значение |
| --- | --- |
| Кандидатов в активной колоде | 25 |
| Приоритетных постеров | первые 8 |
| Цель готовности перед раскрытием | 20 settled-кандидатов |
| Максимальное время ожидания | 2500 ms |
| Минимальное время loader | 180 ms |
| Параллельных сетевых загрузок | 4 |
| Максимальный размер файла | 5 MB |

`settled` означает, что кандидат завершил poster-путь одним из способов:

- найден локальный файл;
- скачан новый preview;
- постер отсутствует;
- загрузка не удалась.

Колода раскрывается, когда:

- все кандидаты settled;
- или settled все приоритетные + достигнут целевой минимум;
- или истек дедлайн 2.5 секунды.

Поэтому отсутствие части постеров в момент раскрытия не всегда баг. Это может быть ожидаемое поведение, чтобы UI не зависал на сети.

### 4. Background prefetch после раскрытия

Если колода не replacement, например локальный top-up или простое обновление без полной замены, постеры ставятся в фон:

```text
CandidatePosterPrefetchController.enqueue_candidates(...)
```

В этом режиме список уже виден, а постеры могут появляться постепенно.

### 5. Как скачивается preview

Для сетевого preview используется:

```text
CandidatePosterPrefetchController
  -> QNetworkAccessManager
  -> normalize_tmdb_poster_download_url(...)
  -> preview_poster_path_for_url(...)
```

TMDb URL нормализуется к preview-size `w342`, чтобы не качать слишком тяжелые изображения.

Файл сохраняется в deterministic preview-cache:

```text
data/cache/posters/images/preview/<sha256(url)[:24]>.jpg
```

При следующем показе того же URL файл будет найден сразу через `local_preview_poster_path_if_cached()`.

### 6. Lazy localized enrichment при выборе карточки

При открытии конкретного кандидата запускается еще один путь:

```text
CandidateListView._start_localized_poster_enrichment(...)
  -> CandidateLocalizedPosterWorker
  -> candidates.pool.localized_posters.ensure_candidate_localized_poster(...)
```

Он нужен, если:

- у кандидата есть `tmdb_id`;
- для текущего `data_language` нет localized-постера;
- или у TV-кандидата не хватает detail-полей.

Worker делает TMDb Details-запрос, собирает localized blocks, обновляет запись кандидата и сохраняет изменения в pool. После этого карточка и список обновляются, а preview download запускается повторно уже с новыми poster hints.

## Почему постер может не загрузиться

### 1. В записи нет poster metadata

Нет ни `poster_url`, ни `poster_path`, ни usable localized fallback.

В диагностике это состояние обычно попадает в `missing`.

Возможные причины:

- TMDb Discover вернул `poster_path=null`;
- TMDb Details не был загружен;
- у тайтла реально нет постера в TMDb;
- запись старая и была импортирована до появления localized/detail enrichment;
- нет `tmdb_id`, поэтому lazy enrichment не может запросить Details.

### 2. Есть metadata, но локальный файл еще не скачан

Есть `poster_url`, но preview-cache файла пока нет.

В диагностике это состояние обычно `metadata_only`.

Это нормальное промежуточное состояние: постер должен появиться после batch/prefetch, если сеть и URL работают.

### 3. Колода раскрылась раньше, чем все постеры готовы

UI не ждет бесконечно. После дедлайна 2.5 секунды список раскрывается, даже если часть сетевых запросов еще идет или уже упала.

Это сделано специально, чтобы вкладка **Кандидаты** не выглядела зависшей.

### 4. URL невалидный

Скачивание не стартует, если URL:

- пустой;
- не начинается с `http://` или `https://`;
- является криво собранным TMDb path;
- содержит path без имени файла.

### 5. Сеть или TMDb CDN временно недоступны

Возможные причины:

- timeout;
- SSL error;
- `403`;
- `429`;
- `500/502/503/504`;
- локальная сеть недоступна;
- CDN обрывает соединение.

Batch-путь через Qt отмечает URL как attempted. Повторные попытки ограничены, чтобы не долбить один и тот же сломанный URL. При следующей активации вкладки старые failed URL могут быть разрешены к retry после паузы.

Bulk-download путь в `posters.download_images.download_preview_posters_for_urls()` делает retries и cooldown:

- до 4 попыток;
- backoff для `403/429`;
- backoff для SSL;
- cooldown после серии ошибок.

### 6. Файл слишком большой или это не изображение

Ограничение:

```text
MAX_POSTER_BYTES = 5 MB
```

Qt-путь дополнительно проверяет, что байты открываются как `QImage`. Если сервер вернул HTML, пустой ответ или поврежденные данные, файл не считается готовым.

### 7. Не удалось записать файл в cache

Даже если сеть вернула картинку, запись может провалиться:

- нет прав на каталог;
- каталог удален во время работы;
- файл занят;
- антивирус блокирует `.tmp` или rename;
- диск недоступен.

В этом случае `_write_preview()` возвращает `None`, и кандидат считается failed для batch.

### 8. Локальный путь есть, но файл отсутствует

Если в записи лежит `poster_path` как локальный путь, UI использует его только если файл реально существует. Просто строка в payload недостаточна.

### 9. Конфликт watched poster cache URL

Для watched-cache есть защита: если текущий candidate `poster_url` не совпадает с URL в poster cache по тому же title/year, default watched poster path не используется. Это защищает от показа постера другого тайтла с похожим названием и годом.

### 10. Lazy localized enrichment еще не успел отработать

Если у кандидата нет постера для текущего языка, но есть `tmdb_id`, запись может обновиться только после выбора карточки или отдельного enrichment-пути. До этого список может показывать placeholder.

### 11. У тайтла есть постер только не в выбранной локали

Логика допускает fallback на другой localized-блок, если он уже есть в записи. Но если другой localized-блок еще не был загружен через Details, fallback не из чего выбрать.

Практически это выглядит так:

- RU-постера нет;
- EN-постер в TMDb есть;
- но EN localized block еще не сохранен в candidate payload;
- до Details enrichment UI видит `missing` или только старый `poster_path`.

### 12. Кандидат был заменен или запрос устарел

GUI использует generation/request ids. Если пользователь быстро переключился между карточками или построилась новая колода, старый poster event может быть проигнорирован, чтобы не подставить картинку в уже другую карточку.

## Диагностика

### Быстрая статистика

Консольная строка:

```text
Candidate pool: <total> | complete: <complete> | posters: <displayable> | need posters: <metadata_only>
```

Она строится через:

```text
candidates.service.get_console_candidate_summary_view()
  -> get_candidate_poster_diagnostics_view()
  -> build_candidate_poster_diagnostics(...)
```

### Состояния постеров

| Состояние | Значение |
| --- | --- |
| `displayable` | уже есть локальный файл: direct local path, preview cache или watched cache. |
| `metadata_only` | URL/path metadata есть, но локального файла еще нет. |
| `missing` | система не нашла usable poster metadata. |

### Что смотреть при баге

1. Есть ли у кандидата `tmdb_id`.
2. Есть ли `localized.<data_language>.poster_url` или `poster_path`.
3. Есть ли fallback localized-блоки.
4. Есть ли root `poster_url` или `poster_path`.
5. Есть ли файл в `data/cache/posters/images/preview/`.
6. Не отличается ли URL candidate от URL watched poster cache по тому же title/year.
7. Не показывается ли колода до завершения batch из-за deadline.
8. Не было ли сетевых ошибок `403/429/timeout/ssl`.

## Важные инварианты

- Вкладка **Кандидаты** строит колоду из локального пула, а не напрямую из TMDb.
- Вектор рекомендаций меняет локальное ранжирование и не должен сам запускать TMDb.
- TMDb-добор запускается только через discovery intent и нехватку локальных кандидатов.
- Активная очередь и резерв не равны всему candidate pool.
- Отсутствие постера не должно блокировать показ кандидата.
- Preview-cache ключуется по URL, а не по title.
- Local poster path считается валидным только если файл существует.
- Если постер есть только в другой локали, он будет показан только если этот fallback уже есть в payload или был загружен через Details enrichment.
