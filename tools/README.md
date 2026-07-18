# Tools

Документ относится к **Watchbane 0.1.1-alpha.1 — Open Route** / **ReDeck v0.1.0**.  
Windows release собирается как folder-based onedir bundle.

Здесь лежат ручные entrypoints. Переиспользуемую логику держать в пакетах `dataset/`, `candidates/`, `storage/`, `apis/`, `posters/`; скрипты — тонкие CLI-обёртки.

## Папки

- `migrations/` — разовые или compatibility-миграции данных.
- `tmdb/` — сборка/refresh/backfill TMDb и network probe.
- `reports/` — сборщики отчётов и quality diagnostics.
- `screenshots/` — локальные helpers для UI-скриншотов.
- `jobs/` — долгие/фоновые maintenance jobs.
- `duplicates/` — ручная проверка дублей.

## Политика вывода

Raw-отчёты по умолчанию — в игнорируемые пути: `data/reports/`, `data/diagnostics/`, `data/exports/`, `tmp/ui/`.

Не писать сгенерированные raw-отчёты в `docs/`. Исторические curated-отчёты — в [`internal/archive/docs/reports/`](../internal/archive/docs/reports/). Активный указатель: [`docs/reports/README.md`](../docs/reports/README.md). См. также [`docs/operations/REPORT_OUTPUT_POLICY.md`](../docs/operations/REPORT_OUTPUT_POLICY.md).
