# dataset

Документ относится к **Watchbane 0.1.1-alpha.1 — Open Route** / **ReDeck v0.1.0**. Каноническая версия: [../VERSION.md](../VERSION.md).

Доменный слой watched-базы Watchbane.

## Целевая структура

```text
dataset/
  service.py              # публичный facade (Phase 2+)
  models/                 # results, identity, schema
  records/                # add, update, delete, features
  meta/                   # meta.json domain logic
  resolve/                # TMDb defaults
  add_flow/               # add-title bundle, preview, save
  transfer/               # candidate → watched
  genres/                 # TMDb genre helpers
  stats/                  # summary, popularity
  analytics/              # read-only score analytics
  views/                  # formatters
```

## Compatibility wrappers

Старые модули в корне `dataset/` остаются re-export wrappers на время миграции:

| Wrapper | Целевой пакет |
|---------|---------------|
| `dataset_records.py` | `records/`, `models/` |
| `storage_movie.py` | `records/` |
| `title_resolve.py` | `resolve/`, `transfer/` |
| `add_title_service.py` | `add_flow/` |
| `delete_record.py` | `records/delete`, `views/` |
| `genre_stats.py` | `genres/` |
| `dataset_stats.py`, `filter_popularity.py` | `stats/` |
| `score_analytics.py` | `analytics/` |

Подробные правила — в [AGENTS.md](AGENTS.md).
