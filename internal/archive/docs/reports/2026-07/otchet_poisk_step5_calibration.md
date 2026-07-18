# Отчёт калибровки FTS5 + BM25 (Step 5.1)

- Дата: 2026-07-10
- Пул: 662 кандидата (production SQLite)
- Набор: 26 bootstrap-запросов в `reports/search/curation/` (rule-based review)

## Метрики

| Этап | W_BM25 / W_FINAL | avg precision@10 |
|------|------------------|------------------|
| Baseline (до калибровки) | 0.4 / 0.6 | **0.549** |
| После grid + aliases + FTS fix | **0.5 / 0.5** | **0.617** |

Порог rollout: **≥ 0.6** — достигнут.

Команды:

```powershell
$env:WATCHBANE_FTS_SEARCH = "1"
py scripts/reports/bootstrap_search_curation.py --sort-mode relevance
py scripts/reports/grid_search_rerank_weights.py
py scripts/reports/summarize_search_eval.py reports/search/curation
```

## Изменения по результатам

### Rerank ([`candidates/search/rerank.py`](candidates/search/rerank.py))

- `W_BM25 = 0.5`, `W_FINAL = 0.5` (grid 0.3–0.7, шаг 0.1).

### Aliases ([`candidates/search/title_aliases.json`](candidates/search/title_aliases.json))

- Расширены: `игра престолов`, жанры (`комедия`, `фантастика`, `драма`, `анимация`), `one piece`.

### FTS MATCH ([`candidates/search/fts_index.py`](candidates/search/fts_index.py))

- Многословные запросы: AND без вложенных OR-групп (`"one"* "piece"*`).
- `OperationalError` в `search_fts` — fallback на typo path.

### Rollout

- `APP_FTS_SEARCH_DEFAULT = True` в [`desktop/settings/app_settings.py`](desktop/settings/app_settings.py).
- Substring fallback в UI только при **явно выключенном** FTS в настройках.

## Слабые запросы (precision &lt; 0.5 на baseline)

Типичные причины: широкие жанровые/годовые запросы, отсутствие тайтла в пуле (`игра престолов`), rule-based review. Ручная доразметка в `reports/search/curation/` приветствуется.

## Скрипты

| Скрипт | Назначение |
|--------|------------|
| `bootstrap_search_curation.py` | batch export + auto-label |
| `grid_search_rerank_weights.py` | подбор W_BM25 / W_FINAL |
| `summarize_search_eval.py` | агрегация precision@10 |

## Следующий цикл (опционально)

- Ручная правка `review` в JSON для спорных запросов.
- Повтор `summarize_search_eval.py` после правок.
- ~~При росте пула до 500+ — SQL pre-filter + FTS join~~ — выполнено в [Step 6](otchet_poisk_step6_performance.md).
