# AGENTS.md — Watchbane

Инструкции для агента (Composer и др.). Читай **перед** любой задачей.

## Источник правды (порядок)

1. [`docs/contracts/PRODUCT_ROADMAP_CONTRACT.md`](docs/contracts/PRODUCT_ROADMAP_CONTRACT.md) — продукт, задача фазы C, колода до 10, «не делать», прогресс фаз.
2. [`VERSION.md`](VERSION.md) — версия релиза.
3. Нужный UI-контракт: [`DESKTOP_STYLE_CONTRACT`](docs/contracts/DESKTOP_STYLE_CONTRACT.md), [`UI_SCALE_CONTRACT`](docs/contracts/UI_SCALE_CONTRACT.md), detail-card contracts.

**Не** брать product direction из [`internal/archive/docs/plans/DESKTOP_GUI_ROADMAP.md`](internal/archive/docs/plans/DESKTOP_GUI_ROADMAP.md) — он **SUPERSEDED** / в архиве.

Слои архитектуры: [`docs/project/AGENTS.md`](docs/project/AGENTS.md).  
Candidates: [`candidates/AGENTS.md`](candidates/AGENTS.md).  
Dataset: [`dataset/AGENTS.md`](dataset/AGENTS.md).

## Продукт (одной фразой)

Watchbane — локальный **inbox рекомендаций**: конечная колода до **10** карточек с постерами; действия **смотрел / сохранить / скрыть**.  
Это разбор кандидатов и ведение списков — **не** «выбор кино на сегодняшний вечер» (V0 в parking). Не каталог, не стриминг, не like/dislike.

## Одна задача = один ID

- Бери ID из PRODUCT_ROADMAP (`C1-01`, `C2-03`, …).
- Не расширяй scope («заодно» запрещено).
- После работы **отметь прогресс** в `PRODUCT_ROADMAP_CONTRACT.md` (чекбокс + журнал).

---

## Scope Gate (STOP перед кодом)

**Перед любыми правками кода** (и перед «сразу сделаю») агент обязан выдать gate-блок и **не писать diff**, пока пользователь не ответит явно: `ок`, `делай`, `ок, делай C1-0x` (с ID).

### Gate-блок (обязательный формат)

```text
Запрос: <кратко своими словами>
Фаза / активный фокус: <из PRODUCT_ROADMAP>
Соответствует фазе C (C0–C4): да / нет
Roadmap ID: <C1-01 | … | НЕТ>
Риски размытия: <1–3 пункта или «нет»>
Предложение: выполнить / отклонить / сузить до <ID>
STOP: код не пишу, пока нет явного «ок» на этот ID
```

Исключения (gate можно сократить до одной строки ID, код сразу):

- пользователь **уже** указал ID и написал «делай / ок» в том же сообщении;
- чисто docs/README/PRODUCT/AGENTS без product-кода **и** с явным ID вроде `D1-*` / «только docs».

### Классификатор запросов

| Тип | Действие |
| --- | --- |
| Есть ID из PRODUCT (`C1-05`, `C2-01`, …) | Gate → ждать «ок» (если ещё не сказано) → делать только ID |
| Баг happy path (колода / постеры / 3 кнопки / пустой экран) | Предложить ближайший ID → ждать «ок» |
| Новая фича / вектор A / B / V0 «Сегодня» / web / like-dislike / LLM | **Отклонить** + риски + куда в backlog |
| Полировка «заодно» / «ещё и …» | Отклонить или вынести в C4 / отдельный ID |
| Рефакторинг «по пути» | Только если **блокирует** текущий ID; иначе отклонить |

### Шаблон отказа (копировать)

> Запрос выходит за фазу C / нет roadmap ID.  
> Риск: снова размыть продукт в поисковик, настройки или новую идею.  
> Могу: (1) отклонить, (2) записать в backlog A/B, (3) сузить до конкретного `C?-??`.  
> **Код не начинаю.**

Активный фокус и запреты «до закрытия» — в шапке раздела 7 [`PRODUCT_ROADMAP_CONTRACT.md`](docs/contracts/PRODUCT_ROADMAP_CONTRACT.md).

---

## UI DoD (фаза C) — обязательно по порядку

UI-задача **не закрыта**, пока не выполнено:

1. **Запуск визуала:** предпочитай `py tools/screenshots/capture_<экран>.py ...`.  
   Live `py start_app.py` — только если нет подходящего capture-скрипта для затронутого экрана.
2. **Скрины** в `screens/tmp_ui/<roadmap_id>/`. Имена:
   - `before_100.png` / `after_100.png` (scale 1.0)
   - `after_125.png` (scale 1.25), если трогали layout
3. **Scales:** только **`1.0`** и **`1.25`** (не требовать 0.75 / 1.5 в фазе C).
4. **Read tool на каждый PNG** → в отчёте 3–6 пунктов: обрезка, overlap, пустота, mojibake, кнопки видны / не видны.
5. **Happy path smoke** (раздел ниже) — да/нет по шагам, если задача касается Recommendations / shell / onboarding.
6. Релевантные **pytest** зелёные.
7. Запрещено писать «UI ок» без пунктов 2–4.

Не коммитить `screens/tmp_ui/` без явной просьбы пользователя.

**Как «нажимать кнопки» (порядок предпочтения):**

1. Capture-скрипт вызывает те же слоты/методы UI программно.
2. В тестах: `QTest.mouseClick` / `keyClick`.
3. Computer use / OS-мышь — только если доступен (см. ниже); иначе не считать задачу проваленной из‑за отсутствия live-кликов.
4. Не симулировать OS-мышь «наугад» и не утверждать, что прокликал окно, если этого не было.

---

## Screenshot tooling (предпочитать)

На Windows скрипты обычно сами ставят `QT_QPA_PLATFORM=windows`. Output → `screens/tmp_ui/<task_id>/`.

| Экран / тема | Команда (пример) |
| --- | --- |
| Onboarding step | `py tools/screenshots/capture_onboarding.py --step welcome --scale 1.0` |
| Onboarding wizard | `py tools/screenshots/capture_onboarding_wizard.py --scale 1.0` |
| Deck reserve | `py tools/screenshots/capture_deck_reserve_indicator.py --scale 1.0 --mode ready` |
| Recommendation controls | `py tools/screenshots/capture_recommendation_controls.py --scale 1.0` |
| Film / detail card | `py tools/screenshots/capture_film_card.py --scale 1.0` |
| User rating | `py tools/screenshots/capture_user_rating_selector.py --scale 1.0` |
| TMDb startup gate | `py tools/screenshots/capture_tmdb_startup_gate.py --scale 1.0` |
| README screens | `py tools/screenshots/capture_readme.py --scale 1.0` |

Повтори с `--scale 1.25`, если менялся layout.

Если скрипта нет для экрана задачи:

- либо минимально расширь существующий capture **в scope задачи**;
- либо live `start_app.py` + сохранение скрина в `screens/tmp_ui/<task_id>/`;
- **не** пропускай визуальную проверку.

---

## Happy path smoke (после onboarding)

Чеклист для задач Recommendations / shell / empty-loading / колоды:

| # | Шаг | Ожидание |
| --- | --- | --- |
| A | Вкладка Рекомендации | открыта первой / без лишних кликов |
| B | Правая область | колода с постерами **или** одно состояние «готовим колоду» |
| C | Карточка | доступны смотрел / сохранить / скрыть |
| D | Chrome UI | нет технического текста у табов, нет обрезки сверху |
| E | Scales 1.0 и 1.25 | без overlap ключевых контролов |

В отчёте по задаче: `A–E: да/нет` одной строкой каждый.

---

## Сеть / TMDb / права

**Разрешено без лишних вопросов:**

- TMDb API с локальным токеном (`TMDB_TOKEN` / `.env.local` / `tmdb.env`);
- `pip` / `pytest` / `compileall`;
- запуск `tools/screenshots/*` и `start_app.py`;
- запись в `screens/tmp_ui/`;
- правки кода **в scope** задачи.

**Запрещено без явной просьбы:**

- `git commit` / `push`;
- удаление пользовательских watched-данных / factory reset;
- правка `hosts` / UAC-обходы без явного запроса задачи;
- SQLite schema / миграции «заодно»;
- печать или коммит токена.

Если sandbox отказал — **сразу запросить нужные permissions (часто `all`) и повторить ту же команду**, не останавливаться на «нужны права».

TMDb в UI-проверке допустим. Долгий replenish / Discover **не смешивать** с критерием «открыл колоду»: один пользовательский этап «готовим колоду».  
Если CDN/сеть упала: скрин с fallback-постером всё равно валиден для проверки layout.

---

## Computer use (если доступен)

**Разрешено:** открыть Watchbane, вкладка Рекомендации, 1–3 действия на карточке (смотрел / сохранить / скрыть), сделать скрин.

**Нельзя:** удалять коллекцию, factory reset, менять hosts, коммитить, печатать токен.

Если computer use **недоступен** — fallback: `tools/screenshots/*` + `QTest`. Задачу **не** считать проваленной только из‑за отсутствия live-кликов.  
**Нельзя** писать «прокликал приложение», если использовался только capture-скрипт без реального computer use — пиши честно: «снято через capture_*».

---

## Анти-паттерны

- «Логика верная, скрин не снимал».
- «Pytest зелёный = UI готов».
- Скрин сделал, но PNG не открывал через Read.
- Закрыл задачу при обрезанном тексте / overlap «потом поправим».
- Утверждал live-клики, когда был только scripted capture.
- Тянул scope («заодно» filters / ranking / web).

---

## Запреты фазы C

- Не переписывать на web.
- Не добавлять LLM / NL / embeddings.
- Не расширять filter algebra (фаза A).
- Не like/dislike вместо смотрел / сохранить / скрыть.
- Не сценарий V0 «Сегодня» / «Смотреть сейчас» в фазе C.
- Не бесконечный каталог вместо конечной колоды.
- Не commit без просьбы пользователя.

---

## Шаблон запроса

```text
Контракт: PRODUCT_ROADMAP_CONTRACT.md
Задача: C1-01
Scope: только то, что в задаче. Не расширять.
Не делать: A, B, web, новые фичи, «заодно»
UI: capture-скрипт → screens/tmp_ui/C1-01/ → Read PNG (1.0 и 1.25) → happy path A–E
После: отметь прогресс в docs/contracts/PRODUCT_ROADMAP_CONTRACT.md
ок, делай C1-01
```

Без ID и без «ок» агент делает только Scope Gate, не код.
