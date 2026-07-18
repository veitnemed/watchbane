# Хранение данных (кратко)

**Источник правды runtime:** `data/watchbane.sqlite3` (watched, meta, candidate pool, criteria, actions, settings, poster metadata).

JSON в `data/watched/`, `data/candidates/` и т.п. — только **legacy import/export/backup**, не активный backend.

Подробный исторический план JSON→SQLite:  
[`internal/archive/docs/plans/DATA_STORAGE_PLAN.md`](../../internal/archive/docs/plans/DATA_STORAGE_PLAN.md).

Миграции:

```powershell
py tools/migrations/migrate_json_to_sqlite.py --dry-run
py tools/migrations/migrate_json_to_sqlite.py --apply
```

Восстановление: сначала backup из `data/backups/`.
