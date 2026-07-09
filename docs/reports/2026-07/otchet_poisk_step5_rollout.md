# Отчёт о проделанной работе — локальный поиск Step 5 (rollout и UX)

- Дата: 2026-07-09
- Ветка: `main`
- Область: rollout FTS через настройки, explainability в desktop, sort UX, query log parity

## Короткий вывод

Реализована кодовая часть Step 5: FTS можно включить из **Настроек** (без обязательного `$env:WATCHBANE_FTS_SEARCH`), в detail card показываются причины текстового совпадения, sort modes `text_relevance` / `relevance` локализованы, query log дополнен полями `text_query` и `fts_enabled`. Substring fallback в UI сохранён при выключенном FTS. **Калибровка весов и default-on** — отдельный ручной этап (5.1), ещё не завершён.

---

## 5.2 Desktop: explainability и sort UX

### Detail card

- `desktop/candidates/presenters.py` — `build_candidate_readonly_detail_entry(..., filters=, search_context=)` вызывает `explain_candidate` при непустом text query и наличии search-сигналов (`matched_fields`, BM25, combined score).
- До 3 строк reasons → `card["search_reasons"]` → `detailTitleMeta` в `desktop/shared/detail/card.py`.
- `desktop/candidates/list_view.py` — detail entry с `last_search_context`, сброс кэша при FTS refresh.

### Sort modes и метрики

- i18n: `candidates.sort.text_relevance`, `candidates.sort.relevance`.
- Метрики списка: `text_relevance_score`, `combined_relevance_score` (раньше показывалось «—»).

### Search input UX

- Placeholder: «Поиск по названию, жанру, описанию…» (ru/en).
- Auto-sort `relevance` при вводе query; восстановление предыдущего mode при очистке (`session.maybe_auto_sort_for_text_query`).

### Query log

- `candidates/search/query_log.py` — optional `text_query`, `fts_enabled` в `build_search_query_entry`.
- `desktop/candidates/list_view.py` — передаёт оба поля; удалён дублирующий `_log_search_query`.

---

## 5.3 Rollout FTS

### Настройка

- `desktop/settings/app_settings.py` — `fts_search_enabled: bool` (default `False`).
- `desktop/settings/ui_scale_control.py` — чекбокс «Полнотекстовый поиск кандидатов».

### Service

- `candidates/service.py` — `is_fts_search_enabled()`:
  - `True` если `WATCHBANE_FTS_SEARCH=1` **или** persisted `fts_search_enabled`;
  - env остаётся override для CI/скриптов.

### Поведение для пользователя

| FTS off (default) | FTS on |
|-------------------|--------|
| Substring по title в UI | Async BM25 по title/жанру/overview |
| Без explain в detail | До 3 строк причин под заголовком |
| Sort вручную | Auto `relevance` при вводе query |

**Не в этом коммите:** default `fts_search_enabled=True`, удаление substring fallback, калибровка `W_BM25` / aliases.

---

## 5.1 Калибровочный цикл (подготовка)

- `scripts/reports/summarize_search_eval.py` — агрегация precision@10 по reviewed JSON в `reports/search/curation/`.

```powershell
$env:WATCHBANE_LOG_SEARCH_QUERIES = "1"
py scripts/reports/export_search_top_results.py --query "..." --sort-mode relevance
py scripts/reports/evaluate_search_relevance.py reports/search/curation/<file>.json
py scripts/reports/summarize_search_eval.py reports/search/curation
```

---

## Проверки

```powershell
py -m compileall candidates storage desktop app diagnostics scripts tests
py -m pytest tests/test_search_document.py tests/test_candidate_fts_index.py tests/test_search_fts_integration.py tests/desktop/test_candidate_search_behavior.py tests/test_search_query_log.py tests/test_ui_scale_settings.py::test_save_then_load_fts_search_setting -q
```

Результат: **40 passed**.

---

## Включение FTS

- UI: **Настройки** → «Полнотекстовый поиск кандидатов» → **Сохранить**.
- Env override: `$env:WATCHBANE_FTS_SEARCH = "1"`.
- Запрос вводится в поле поиска на вкладке **Кандидаты** (после применения фильтров).

---

## Изменённые / новые файлы (функциональные)

| Файл | Изменение |
|------|-----------|
| `candidates/service.py` | settings-aware `is_fts_search_enabled` |
| `candidates/search/query_log.py` | `text_query`, `fts_enabled` |
| `desktop/settings/app_settings.py` | `fts_search_enabled` |
| `desktop/settings/ui_scale_control.py` | чекбокс FTS |
| `desktop/candidates/presenters.py` | explain + sort i18n/metrics |
| `desktop/candidates/list_view.py` | FTS detail, auto-sort, log |
| `desktop/candidates/session.py` | auto-sort restore |
| `desktop/shared/detail/card.py` | `search_reasons` в meta |
| `desktop/i18n/catalog.py` | placeholder, sort, settings strings |
| `scripts/reports/summarize_search_eval.py` | *(новый)* |
| `tests/...` | FTS settings, explain, query log |

---

## Следующие шаги

1. 20–30 размеченных запросов с `WATCHBANE_LOG_SEARCH_QUERIES=1`.
2. `summarize_search_eval.py` → precision@10.
3. При ≥ 0.6 — weights/aliases + default `fts_search_enabled=True`.
4. Убрать substring fallback после default-on релиза.
