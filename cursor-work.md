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
| Активный фокус | `C1-02` (happy path 6 шагов) |
| UI QA scales | `1.0` и `1.25` |
| Последний релевантный коммит | (C1-01 — см. журнал ниже) |

**Цель простыми словами:** разобрать порцию рекомендаций в списки, а не «выбрать кино на вечер».

**Дальше по плану:** `C1-02` → … (см. PRODUCT §10), только после Scope Gate + «ок».

---

## Журнал

### 2026-07-19 — C1-01
- **Запрос:** коммит docs (`cursor-work`) + первый шаг C1-01
- **Сделано:** Recommendations = default shell tab; `DEFAULT_SHELL_TAB_ID`; focus после build и после TMDb gate без onboarding; PRODUCT + тесты
- **Файлы / коммит:** `desktop/shell/tabs.py`, `desktop/shell/main_window.py`, tests, PRODUCT, cursor-work
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

## Открытый backlog (не код до «ок»)

1. `C1-02` — Happy path из 6 шагов  
2. `C1-03` … `C2-07` — по порядку PRODUCT §10  
3. Код колоды 25→10 — отдельный ID  
4. V0 / A / B — только после явного решения (parking)
