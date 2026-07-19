# cursor-work.md — отчёт по работе Cursor / агентов

**Назначение:** живой журнал изменений в репозитории Watchbane, который ведёт агент после каждой осмысленной сессии или закрытого roadmap ID.

**Канон продукта:** [`docs/contracts/PRODUCT_ROADMAP_CONTRACT.md`](docs/contracts/PRODUCT_ROADMAP_CONTRACT.md)  
**Правила агента:** [`AGENTS.md`](AGENTS.md)

---

## Как вести этот файл

После задачи агент **дописывает** запись сверху журнала (новые сверху):

```markdown
### YYYY-MM-DD — <ID или тема>
- **Запрос:** …
- **Сделано:** …
- **Файлы / коммит:** …
- **Проверка:** …
- **Не сделано / next:** …
```

Не дублировать весь PRODUCT — сюда краткий отчёт «что реально сделали в git/чате».

---

## Сейчас (снимок)

| Поле | Значение |
| --- | --- |
| Продуктовый контур | **X — inbox-колода** (смотрел / сохранить / скрыть) |
| Не делаем | V0 «Сегодня», A/B (parking), web, LLM |
| Активный фокус | `C2-02` (два основных состояния колоды и отдельное error-состояние) |
| UI QA scales | `1.0` и `1.25` |
| Последний релевантный commit | C0-01…C0-03 (этот commit) |

**Цель простыми словами:** разобрать порцию рекомендаций в списки, а не «выбрать кино на вечер».

**Дальше по плану:** `C2-02` → `C2-04` (см. PRODUCT §10), только после Scope Gate + «ок».

---

## Журнал

### 2026-07-19 — C2-01
- **Запрос:** сделать единый empty/loading overlay в правой области Recommendations.
- **Сделано:** loading-экран использует один явно именованный overlay с copy «Подготавливаем рекомендации» и прогрессом постеров; capture умеет снять именно это состояние без подмены runtime-данных.
- **Файлы / commit:** `desktop/candidates/list_view.py`, `tests/desktop/test_candidate_deck_reveal.py`, `tools/screenshots/capture_readme.py`, PRODUCT, happy path, `cursor-work.md`; commit будет создан отдельным шагом.
- **Проверка:** compileall; targeted Qt pytest с `PYTEST_QT_API=pyqt6`; native capture + Read PNG 1.0 / 1.25.
- **Не сделано / next:** C2-02 — закрепить только preparing / ready как основные состояния и отдельный error.

### 2026-07-19 — C2-03
- **Запрос:** показывать колоду с постерами через один экран ожидания.
- **Сделано:** готовая колода больше не открывается до первой poster batch; `recommendationsDeckLoadingPage` остаётся единственным экраном ожидания и закрывается после готовности партии или fallback.
- **Файлы / commit:** `desktop/candidates/list_view.py`, `tests/desktop/test_candidate_deck_reveal.py`, PRODUCT, `cursor-work.md`; commit будет создан отдельным шагом по запросу.
- **Проверка:** compileall; targeted Qt pytest 7 passed с `PYTEST_QT_API=pyqt6`; capture + Read PNG 1.0 / 1.25.
- **Не сделано / next:** C2-01 / C2-02 — привести loading/empty/error к единому контракту состояний.

### 2026-07-19 — C1-06
- **Запрос:** сделать три действия на карточке рекомендаций одновременно доступными и понятными.
- **Сделано:** оценка для действия «смотрел» получила явную подпись «Смотрел — оцените»; «+ Запомнить» и «× Не показывать» сохранены отдельными видимыми кнопками.
- **Файлы / commit:** i18n, UI-regression test, PRODUCT, `HAPPY_PATH_INBOX.md`, `cursor-work.md`; commit будет создан отдельным шагом по запросу.
- **Проверка:** compileall; targeted Qt pytest 4 passed с `PYTEST_QT_API=pyqt6`; capture + Read 1.0 / 1.25.
- **Не сделано / next:** C2-03 — показывать колоду с постерами через один экран ожидания.

### 2026-07-19 — C1-05
- **Запрос:** сделать конечную пользовательскую колоду до 10 карточек и одну CTA после её окончания.
- **Сделано:** `ACTIVE_DECK_SIZE` = 10; действия не подставляют резервные карточки в активную колоду; «Ещё варианты» появляется только после последней карточки; сохранённые колоды старого размера инвалидируются версией схемы.
- **Файлы / commit:** `candidates/recommendation_deck_service.py`, `desktop/candidates/list_view.py`, i18n, тесты, PRODUCT, `HAPPY_PATH_INBOX.md`, `cursor-work.md`; commit будет создан отдельным шагом по запросу.
- **Проверка:** compileall; service 29 passed; reserve 12 passed; Qt targeted 3 passed и orchestration 2 passed с `PYTEST_QT_API=pyqt6`; capture + Read PNG 1.0 / 1.25.
- **Не сделано / next:** C1-06 — три действия на карточке сделать однозначными с первого взгляда.

### 2026-07-19 — C1-04
- **Запрос:** скрыть с главного экрана Recommendations вайб-контролы и лишние пресеты.
- **Сделано:** подтверждён и закреплён regression-тестом контракт: пресеты и вайб-контролы находятся только в отдельной вкладке «Настройки поиска», а не в `CandidateListView`.
- **Файлы / commit:** `tests/test_desktop.py`, PRODUCT, `HAPPY_PATH_INBOX.md`, `cursor-work.md`; commit будет создан отдельным шагом по запросу.
- **Проверка:** targeted pytest; capture Recommendations и Read PNG на 1.0 / 1.25.
- **Не сделано / next:** C1-05 — ограничить пользовательскую колоду десятью карточками и показать единственную CTA после её окончания.

### 2026-07-19 — C1-03
- **Запрос:** выполнить daily path без обязательного перехода в «Настройки поиска».
- **Сделано:** закреплено, что Recommendations строит колоду на `DEFAULT_BROWSE_FILTERS`, когда пользователь не открывал форму поиска; добавлен регрессионный тест этого инварианта.
- **Файлы / commit:** `desktop/candidates/list_view.py`, `tests/test_desktop.py`, PRODUCT, `cursor-work.md`; commit не создан — не запрашивался.
- **Проверка:** targeted pytest; capture Recommendations и Read PNG на 1.0 / 1.25.
- **Не сделано / next:** `C2-01` остаётся активным ID.

### 2026-07-19 — C0-03
- **Запрос:** синхронизировать строгий план и текущий рабочий ID.
- **Сделано:** PRODUCT назначен единственным источником текущего ID; активный ID приведён к `C2-01` по PRODUCT §10; «вечерний путь» заменён на путь разбора рекомендаций; C2-02 описывает два основных и отдельное error-состояние; дублирующий backlog удалён из этого журнала.
- **Файлы / commit:** `docs/contracts/PRODUCT_ROADMAP_CONTRACT.md`, `cursor-work.md`; commit создан в этой сессии.
- **Проверка:** docs-only review: активный ID, следующий ID и порядок PRODUCT §10 согласованы.
- **Не сделано / next:** `C2-01` — только после нового Scope Gate и явного «ок».

### 2026-07-19 — C0-02
- **Запрос:** задать строгий критерий проверки продуктовой гипотезы.
- **Сделано:** добавлены условия подтверждения после C3 и правило опровержения: при провале не открывать A/B/V0 и C4 автоматически.
- **Файлы / commit:** `docs/contracts/PRODUCT_ROADMAP_CONTRACT.md`, `cursor-work.md`; commit создан в этой сессии.
- **Проверка:** docs-only review: S1–S6 отделены от проверки реальной полезности inbox.
- **Не сделано / next:** провести проверку только после рабочего C1–C3.

### 2026-07-19 — C0-01
- **Запрос:** зафиксировать конкретную продуктовую постановку задачи.
- **Сделано:** в PRODUCT добавлена гипотеза: автор разбирает небольшую колоду неизвестных кандидатов, чтобы поддерживать актуальные watched / saved / hidden без бесконечного каталога; обозначены проблема, альтернатива и ожидаемый результат сессии.
- **Файлы / коммит:** `docs/contracts/PRODUCT_ROADMAP_CONTRACT.md`; включён в общий docs commit C0-01…C0-03.
- **Проверка:** docs-only review: формулировка не добавляет V0, A/B, web или новую продуктовую функцию.
- **Не сделано / next:** C0-02 и C0-03 выполнены в следующих записях; следующий рабочий ID — `C2-01`.

### 2026-07-19 — C1-02
- **Запрос:** сделать C1-02, коммит, отдельный блок UX
- **Сделано:** `docs/contracts/HAPPY_PATH_INBOX.md` — 6 шагов, маппинг смотрел→оценка / сохранить / скрыть, чеклист, разрывы → C1-03…C1-06; ссылки в PRODUCT §6 и AGENTS; C1-02 `[x]`; фокус → C1-03
- **Файлы / коммит:** `5a42533` (`HAPPY_PATH_INBOX.md`, PRODUCT, AGENTS, cursor-work)
- **Проверка:** capture → `screens/tmp_ui/C1-02/` + Read (deck_list, deck_ready, rating); A–E: да/частично по таблице в HAPPY_PATH; код UI не меняли
- **Не сделано / next:** C1-03; размер колоды 10 и одна CTA (C1-05); явные 3 кнопки (C1-06)

### 2026-07-19 — C1-01
- **Запрос:** коммит docs (`cursor-work`) + первый шаг C1-01
- **Сделано:** Recommendations = default shell tab; `DEFAULT_SHELL_TAB_ID`; focus после build и после TMDb gate без onboarding; PRODUCT + тесты
- **Файлы / коммит:** `25179cc` → `origin/main` (`tabs.py`, `main_window.py`, tests, PRODUCT, cursor-work)
- **Проверка:** 6 pytest зелёные; скрин `screens/tmp_ui/C1-01/after_100.png` (Read): вкладка «Рекомендации» первая и активная; A да, B да (список), C н/д (не цель), D да, E 1.0 only (layout не трогали)
- **Не сделано / next:** C1-02; колода 25→10; empty overlay

### 2026-07-19 — создать `cursor-work.md`
- **Запрос:** вести md-отчёт по изменениям `cursor-work.md`
- **Сделано:** файл создан; зафиксирован снимок состояния и бэклог сессий D0–X
- **Файлы / коммит:** `d91eef2` → `origin/main`
- **Проверка:** docs only
- **Не сделано / next:** код C1-01 (сделан в записи выше)

### 2026-07-19 — канон вариант X
- **Запрос:** зафиксировать X (inbox), обновить docs, commit + push
- **Сделано:** PRODUCT v1.4 — inbox vs «вечер»; A/B/V0 = parking; обновлены README, AGENTS, rules
- **Файлы / коммит:** `a80b7ea` → `origin/main`
- **Проверка:** docs only
- **Не сделано / next:** C1-01

### 2026-07-18 — Scope Gate (S0)
- **Запрос:** строгий STOP перед out-of-scope кодом
- **Сделано:** секция Scope Gate в AGENTS; `.cursor/rules/scope-gate.mdc`; PRODUCT v1.3
- **Файлы / коммит:** `fa9e003`
- **Проверка:** docs only
- **Не сделано / next:** —

### 2026-07-18 — AGENTS UI DoD (D1-D)
- **Запрос:** дописать визуал, скрины, capture-скрипты, happy path
- **Сделано:** полный AGENTS DoD + `product-phase-c.mdc`
- **Файлы / коммит:** вошло в `2a78df0` / уточнения рядом с S0
- **Проверка:** docs only

### 2026-07-18 — D1 docs cleanup + RU
- **Запрос:** архив отчётов/планов, русская документация, хаб
- **Сделано:** reports/plans → `internal/archive/docs/`; активные contracts/arch/ops на RU; корневой AGENTS
- **Файлы / коммит:** `2a78df0`
- **Проверка:** `tests/test_runtime_reports.py` — 12 passed (путь template → archive)
- **Не сделано / next:** не коммитили `screens/`, `desktop/images/ui_9*`, шум `start_app.py`

### 2026-07-17 — D0 PRODUCT_ROADMAP
- **Запрос:** контракт продукта и roadmap с чекбоксами
- **Сделано:** создан `PRODUCT_ROADMAP_CONTRACT.md`; колода 10; scales 1.0/1.25
- **Файлы / коммит:** позже вошло в docs-коммиты
- **Проверка:** docs only

---

Текущий рабочий ID и порядок задач берутся только из PRODUCT §7 и §10; этот файл — журнал, не второй roadmap.
