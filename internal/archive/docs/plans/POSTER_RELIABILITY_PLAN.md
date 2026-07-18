# Poster Reliability Plan

## Проверка На Рабочем Профиле (2026-07-11)

План сверялся не только по коду, но и на активном профиле пользователя:

- пул: 305 кандидатов;
- локально готовы: 147 постеров;
- ещё не скачаны, но имеют корректный URL: 158;
- без metadata: 0;
- текущая колода из 25 кандидатов требовала 5 сетевых загрузок;
- построение колоды заняло 85.5 мс;
- все 5 загрузок завершились сетевой ошибкой за 2.14 с;
- прямое подключение к `image.tmdb.org` на этой машине также завершилось ошибкой подключения.

Следствие: это не потеря RU-постеров и не отсутствие URL в пуле. При недоступном CDN текущая реализация ждала до 2.5 секунд, а затем открывала колоду с обычными пустыми заглушками. Первый этап реализации должен стабилизировать этот внешний сбой: быстро переводить карточки в fallback-состояние, не повторять одинаково обречённые запросы на каждой новой колоде и не блокировать интерфейс. Реальный повтор загрузки остаётся возможным после краткого cooldown, когда сеть восстановится.

После реализации host cooldown были дополнительно проверены сценарии active deck:

| Сценарий | Построение колоды | Нужна сеть | Результат при недоступном CDN |
| --- | ---: | ---: | --- |
| Без фильтров | 63.5 мс | 5 из 25 | fallback за 1.16 с |
| Только фильмы | 54.0 мс | 22 из 25 | fallback за 1.22 с |
| Только сериалы | 61.6 мс | 5 из 25 | без зависания очереди |
| Россия | 59.8 мс | 12 из 25 | без серии повторных подключений |
| US-сериалы | 56.6 мс | 5 из 25 | без серии повторных подключений |

### Реализованный Первый Шаг

`CandidatePosterPrefetchController` теперь распознаёт ошибки подключения CDN (`connection refused`, DNS, timeout, SSL и аналогичные сетевые ошибки) и ставит конкретный host на 60 секунд на паузу. Уже ожидающие URL этого host завершаются как fallback, не создавая новые подключения. После истечения паузы следующий показ снова попробует загрузить настоящий постер. Это сохраняет быстрый интерфейс при временно недоступной сети, не меняя рейтинг, фильтры, состав колоды или данные пользователя.

Цель: убрать пользовательскую ситуацию, когда в активной колоде рекомендаций карточки выглядят как "постеры не загрузились".

Важно: технически нельзя гарантировать реальный постер для каждого тайтла. У части тайтлов постера может не быть в TMDb, сеть может быть недоступна, CDN может вернуть ошибку, локальный диск может не дать записать файл. Поэтому целевой контракт не "у каждого тайтла всегда есть настоящий постер", а жестче и честнее:

```text
Перед показом активной колоды каждый кандидат должен быть в одном из состояний:
1. ready: есть валидный локальный poster image;
2. fallback_ready: настоящего постера нет или он недоступен, но показан стабильный красивый placeholder;
3. deferred: кандидат не попадает в активную колоду до следующей попытки.
```

`metadata_only` и `missing` не должны молча попадать в видимый список как пустые постеры.

## Что сейчас создает проблему

По отчету текущая архитектура допускает несколько нормальных, но визуально плохих промежуточных состояний.

1. Колода строится быстрее, чем догружаются постеры.

`CandidateListView` раскрывает список, когда settled все приоритетные кандидаты, достигнут минимум settled, или истек дедлайн 2.5 секунды. `settled` сейчас включает и успех, и отсутствие metadata, и сетевой fail. Поэтому список может открыться с частью пустых постеров.

2. `metadata_only` считается приемлемым промежуточным состоянием.

Если есть `poster_url`, но preview-файл еще не скачан, кандидат остается в активной колоде. Это хорошо для скорости, но плохо для ощущения готового интерфейса.

3. `missing` не ремонтируется до показа колоды.

Если у кандидата нет poster metadata для текущего языка, lazy enrichment запускается только при выборе карточки. В списке такой кандидат может уже выглядеть пустым.

4. Fallback на другую локаль зависит от того, что fallback-блок уже сохранен в payload.

Если RU-постера нет, но EN-постер есть в TMDb, UI покажет EN только если этот block уже был загружен через Details.

5. Нет постоянного реестра poster failures.

Сейчас есть in-memory attempted/failed для GUI batch, но нет полноценного устойчивого статуса: какой URL падал, почему, когда retry, надо ли исключать кандидата из активной колоды.

6. Диагностика есть, но она не является gate для активной колоды.

`displayable`, `metadata_only`, `missing` считаются, но deck selection не использует это как обязательное условие качества.

## Целевой UX

Пользователь не должен видеть "случайно пустые" постеры.

Допустимые видимые состояния:

- настоящий постер;
- аккуратный fallback-постер с названием, годом и типом контента;
- явный статус "постер недоступен", если это действительно no-poster/failed после попыток, но не пустая область и не ощущение недогрузки.

Недопустимые состояния:

- карточка в активной колоде без картинки из-за того, что preview еще качается;
- карточка без картинки из-за того, что Details enrichment еще не запускался;
- массовое раскрытие колоды с пустыми постерами после 2.5 секунд;
- тихий fail CDN без повторной стратегии и без fallback.

## План Работ

### Этап 1. Ввести poster readiness contract

Добавить отдельную доменную классификацию для кандидата:

```text
PosterReadiness:
  ready
  needs_metadata
  needs_download
  downloading
  failed_retryable
  failed_permanent
  no_poster
  fallback_ready
```

Текущих `displayable`, `metadata_only`, `missing` недостаточно, потому что они не отвечают на вопрос: "можно ли показывать кандидата в активной колоде прямо сейчас?"

Где делать:

- новый небольшой модуль рядом с `candidates.pool.diagnostics` или `desktop.candidates.poster_prefetch`;
- использовать существующие `build_poster_hints_from_candidate()`, `resolve_local_poster_path_for_candidate()`, `candidate_needs_tmdb_detail_enrichment()`.

Инвариант:

```text
CandidateListView не раскрывает active deck как готовую, пока каждый visible candidate не ready или fallback_ready.
```

### Этап 2. Предзагрузка metadata до показа колоды

Перед batch-download постеров надо сначала закрывать состояние `needs_metadata`.

Для active deck:

1. взять первые 25 кандидатов;
2. найти кандидатов с `tmdb_id`, у которых нет usable poster hints или нет localized fallback;
3. пачкой выполнить Details enrichment до poster batch;
4. сохранить обновленные candidate payload в pool;
5. пересобрать poster hints;
6. только потом запускать download batch.

Важно ограничить нагрузку:

- максимум 25 кандидатов active deck;
- максимум 4 concurrent Details-запроса или последовательный worker с progress;
- не делать повторный Details, если `tmdb_detail_fields_checked_at` свежий;
- не блокировать навсегда, если TMDb недоступен.

Результат:

- кейс "RU нет, EN есть, но EN block еще не загружен" закрывается до показа списка;
- старые записи без localized poster получают шанс восстановиться автоматически.

### Этап 3. Перестроить reveal gate

Сейчас gate завязан на `settled`, а `settled` может означать fail. Нужно заменить критерий раскрытия.

Новый gate:

```text
reveal allowed, если:
  все visible candidates = ready или fallback_ready
или:
  истек hard timeout, но все unresolved candidates заменены fallback_ready placeholder
```

То есть дедлайн больше не должен раскрывать пустые постеры. Дедлайн может только переключить unresolved в placeholder/fallback.

Текущие константы можно оставить как стартовые:

- minimum loader: 180 ms;
- soft target: первые 8 и 20 settled;
- hard timeout: 2.5 s.

Но после hard timeout нужно не "показать как есть", а:

1. завершить UI-подготовку;
2. для unresolved поставить fallback poster;
3. продолжить сетевые retry в фоне;
4. при успехе заменить fallback на настоящий poster.

### Этап 4. Не пускать плохие poster candidates в active при наличии альтернатив

Deck service сейчас ранжирует по рекомендационной логике, не по готовности постера. Нужно добавить UI-level replacement policy, чтобы не ломать recommendation scoring.

После построения deck:

1. проверить active на poster readiness;
2. если кандидат `failed_permanent` или `no_poster`, попробовать заменить его кандидатом из reserve с `ready` или `needs_download`;
3. если ready-кандидатов в reserve нет, оставить кандидата, но сразу использовать fallback;
4. не менять сам ranking core, чтобы логика рекомендаций не зависела от GUI.

Это лучше делать в `CandidateListView` или небольшом helper для UI preparation, а не внутри `RecommendationDeckService`.

Причина: отсутствие постера это presentation-readiness, а не качество рекомендации.

### Этап 5. Persistent poster failure registry

Нужен локальный журнал по URL и/или TMDb identity:

```text
poster_fetch_status:
  poster_url
  tmdb_id
  media_type
  status
  reason
  attempts
  last_attempt_at
  next_retry_at
  local_path
```

Что это даст:

- не пытаться бесконечно качать битый URL на каждом открытии;
- отличать временную сеть от постоянного `404/no image`;
- показывать fallback сразу, если известно, что URL недавно падал;
- автоматически retry позже;
- иметь диагностический отчет "почему нет постера".

Минимальный вариант без новой таблицы: settings/json cache рядом с poster cache. Лучший вариант для проекта: SQLite repository рядом с `storage.sqlite.poster_repository`.

### Этап 6. Единая стратегия retry

Сейчас bulk-download и Qt-prefetch отличаются. Нужно унифицировать правила:

- retryable: timeout, SSL, network, `429`, `500`, `502`, `503`, `504`;
- возможно retryable с backoff: `403`;
- permanent: invalid URL, empty URL, corrupt image после нескольких попыток, oversized, no poster metadata после Details;
- retry schedule: 5 min, 30 min, 6 hours, 24 hours;
- ручной reset/retry через diagnostic action позже.

Qt-prefetch должен писать reason, а не просто failed count.

### Этап 7. Fallback poster component

Даже при идеальном pipeline настоящего постера может не быть. Поэтому нужен профессиональный fallback, а не пустота.

Fallback должен быть deterministic и выглядеть как часть интерфейса:

- фон по media type или genre;
- title;
- year;
- маленький бейдж `Movie` / `Series`;
- возможно первая буква/монограмма;
- тот же aspect ratio, что у постера;
- не ломает размеры карточек.

Где использовать:

- list model/delegate;
- detail card;
- loading/reveal hard timeout;
- no-poster/permanent-fail состояние.

Инвариант UI:

```text
Карточка кандидата всегда имеет визуальную poster surface одного размера.
```

### Этап 8. Prewarm после TMDb-добора

После `replenish_candidate_pool_for_filters()` новые кандидаты импортируются в pool, но preview-файлы могут быть не скачаны.

Нужно добавить post-import prewarm:

1. взять `added_pool_keys`;
2. загрузить соответствующие кандидаты;
3. выполнить metadata enrichment для missing poster hints;
4. поставить poster URLs в download queue;
5. прогресс добора считать не только по accepted candidates, но и по poster readiness.

UX:

```text
Ищем и пополняем: 30 / 30
Готовим постеры: 24 / 30
```

После этого вкладка **Кандидаты** открывается уже на прогретом pool.

### Этап 9. Диагностический экран/отчет

Существующую диагностику нужно расширить:

```text
displayable
metadata_only
missing
failed_retryable
failed_permanent
no_poster
fallback_ready
```

Для problem rows показывать:

- title;
- year;
- media type;
- tmdb_id;
- poster_url;
- source;
- readiness;
- failure reason;
- attempts;
- next retry.

Это нужно не для пользователя в основном UI, а для отладки и регрессий.

### Этап 10. Тесты

Минимальные regression tests:

1. Кандидат с `localized.ru.poster_url` и готовым preview становится `ready`.
2. Кандидат с `poster_url`, но без файла становится `needs_download`.
3. Кандидат без RU poster, но с EN fallback выбирает EN poster.
4. Кандидат без poster metadata и с `tmdb_id` становится `needs_metadata`.
5. После Details enrichment candidate получает fallback localized poster.
6. Invalid URL не попадает в бесконечный download loop.
7. Hard timeout reveal не оставляет unresolved poster surface пустым.
8. Active deck preparation заменяет no-poster кандидата из reserve, если есть ready-замена.
9. Если замены нет, используется fallback poster, а layout не меняется.
10. После filter replenish post-import prewarm ставит новые poster URLs в очередь.

UI tests:

- `tests/desktop/test_candidate_poster_prefetch.py`;
- `tests/desktop/test_candidate_deck_reveal.py`;
- `tests/test_search_core.py` для диагностики;
- новый focused test на poster readiness contract.

## Приоритетная Реализация

### Шаг 1. Быстрый защитный слой

Сделать fallback poster обязательным в list/detail, чтобы пустых областей не было даже до полной архитектурной доработки.

Результат: пользователь больше не видит "сломанный" постер, даже если сеть упала.

### Шаг 2. Исправить reveal gate

Дедлайн больше не раскрывает unresolved как пустые. Перед раскрытием unresolved переводятся в fallback-ready.

Результат: экран подготовки больше не заканчивается визуально пустой колодой.

### Шаг 3. Pre-enrich active deck metadata

Перед poster batch выполнить Details enrichment для active candidates с `needs_metadata`.

Результат: закрываются старые записи и локали, где постер есть только не в текущем payload.

### Шаг 4. Poster readiness diagnostics

Добавить read-only диагностику readiness/failure reason.

Результат: можно понять, это "нет постера в TMDb", "сеть", "битый URL", "не скачан cache" или "не было Details".

### Шаг 5. Persistent failure registry и retry

Добавить постоянный статус попыток.

Результат: система перестает повторять одни и те же ошибки и умеет повторять временные failures осмысленно.

### Шаг 6. Prewarm после добора

После TMDb-добора готовить постеры новых кандидатов до перехода в рекомендации.

Результат: новые 30 кандидатов не появляются как "голые" записи без изображений.

## Definition Of Done

Фича считается законченной, когда выполняются условия:

- В активной колоде нет карточек с пустой poster area.
- `metadata_only` не считается готовым состоянием для visible active deck.
- `missing` перед показом проходит Details enrichment, если есть `tmdb_id`.
- Если реального постера нет, показывается fallback poster.
- Hard timeout подготовки не приводит к пустым постерам.
- После TMDb-добора новые кандидаты проходят poster prewarm.
- Диагностика показывает причину для каждого не-настоящего постера.
- Есть тест на reveal timeout без пустых poster surfaces.
- Есть тест на fallback localized poster.
- Есть тест на invalid URL без бесконечного retry.

## Что не нужно делать

- Не блокировать UI бесконечно до настоящего постера.
- Не удалять хороший кандидат только потому, что у него нет постера в TMDb.
- Не смешивать recommendation ranking и poster availability в core scoring.
- Не качать full-size изображения, если достаточно preview `w342`.
- Не делать сетевые запросы из delegate/model при рисовании списка.
