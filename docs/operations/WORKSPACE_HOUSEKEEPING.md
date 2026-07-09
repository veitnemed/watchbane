# Workspace Housekeeping

This project keeps generated data and visual-check artifacts out of git. The
repository should stay small enough to clone and review without local caches,
database dumps or one-off screenshots.

## UI Screenshots

- Committed product screenshots live in `screens/`.
- Temporary UI smoke screenshots live in `screens/tmp_ui/`.
- `screens/tmp_ui/.gitkeep` is tracked so the folder exists after clone.
- Files under `screens/tmp_ui/` are ignored and can be deleted or regenerated.

When checking desktop UI changes, keep screenshots grouped by task under
`screens/tmp_ui/tmp_ui_*` instead of creating root-level `tmp_ui_*` folders.

## Reports

Generated reports belong in ignored output folders, not in the active `docs/`
root. Default raw report locations are documented in
[REPORT_OUTPUT_POLICY.md](REPORT_OUTPUT_POLICY.md).

Use `docs/reports/<topic>/` only for short curated summaries that should remain
part of project documentation. Do not commit raw generated markdown, JSON dumps,
network logs, visual smoke screenshots, cache snapshots or one-off audit
transcripts.

## Large Local Artifacts

These paths are intentionally ignored and should not be committed:

- `datasets/` - local datasets, including IMDb sqlite databases.
- `data/cache/` - rebuildable API/cache data.
- `data/backups/` - local backup snapshots.
- `data/exports/` - generated export archives and candidate-pool outputs.
- `data/watchbane.sqlite3*` - local SQLite runtime data.
- `data/candidates/*.json*` and `data/watched/*.json*` - legacy import/export or old local data.
- `reports/` and `data/diagnostics/` - generated diagnostics.
- `logs/` - generated local logs.

The public desktop and candidate flows are TMDb-only. A local IMDb sqlite
database and KP API artifacts are not required for normal app use. If an
internal legacy helper needs `datasets/dataset_sql_light/imdb_light.sqlite3`,
restore it locally; do not commit it.

## Cleanup Candidates

Safe cleanup targets when the workspace gets large:

- old `screens/tmp_ui/tmp_ui_*` screenshot batches;
- raw generated reports under `reports/`;
- generated release zip files under `data/exports/`;
- old `pool.before_*.json` snapshots after confirming the active pool is valid;
- rebuildable TMDb cache files under `data/cache/tmdb/`;
- local IMDb sqlite databases under `datasets/`.

Do not delete `data/watchbane.sqlite3` unless you intentionally reset local
data or have restored a backup. Legacy JSON files are not canonical runtime
storage after the SQLite cutover.
