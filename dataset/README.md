# dataset

Доменный слой watched-базы Watchbane.

## Целевая структура

```text
dataset/
  service.py              # публичный facade (Phase 2+)
  models/                 # results, identity, schema
  records/                # add, update, delete, features
  meta/                   # meta.json domain logic
  resolve/                # SQL/KP/TMDb defaults
  add_flow/               # add-title bundle, preview, save
  transfer/               # candidate → watched
  excel/                  # export/import
  tags/                   # vibe tag mutations
  genres/                 # mapping, catalog, API import
  stats/                  # summary, popularity
  analytics/              # read-only score analytics
  views/                  # formatters
```

## Compatibility wrappers

Старые модули в корне `dataset/` остаются re-export wrappers на время миграции:

| Wrapper | Целевой пакет |
|---------|---------------|
| `dataset_records.py` | `records/`, `models/` |
| `storage_movie.py` | `records/`, `excel/` |
| `title_resolve.py` | `resolve/`, `transfer/`, `genres/` |
| `add_title_service.py` | `add_flow/` |
| `delete_record.py` | `records/delete`, `views/` |
| `excel_work.py` | `excel/` |
| `genre_import.py`, `genre_stats.py` | `genres/` |
| `tags_work.py` | `tags/` |
| `dataset_stats.py`, `filter_popularity.py` | `stats/` |
| `score_analytics.py` | `analytics/` |

Подробные правила — в [AGENTS.md](AGENTS.md).
