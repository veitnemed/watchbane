# Tools

Документ относится к **Watchbane 0.1.1-alpha.1 — Open Route** / **ReDeck v0.1.0**. Windows release собирается как folder-based onedir bundle.

Manual entrypoints live here. Reusable application logic belongs in active
packages such as `dataset/`, `candidates/`, `storage/`, `apis/` or `posters/`;
scripts should stay thin CLI wrappers.

## Folders

- `migrations/` - explicit one-off or compatibility data migrations.
- `tmdb/` - TMDb build, refresh, backfill and network probe utilities.
- `reports/` - report builders and quality diagnostics.
- `screenshots/` - local UI screenshot capture helpers.
- `jobs/` - long-running or background maintenance jobs.
- `duplicates/` - manual duplicate inspection tools.

## Output Policy

Raw reports should default to ignored paths under `data/reports/`, `data/diagnostics/`,
`data/exports/` or `tmp/ui/`.

Do not write generated raw reports into `docs/`. Curated summaries that should
be committed belong under `docs/reports/<topic>/`.
