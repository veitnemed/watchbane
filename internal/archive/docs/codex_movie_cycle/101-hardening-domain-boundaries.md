# 101 Hardening Domain Boundaries

Date: 2026-07-08

Reviewed:
- Direct JSON/dataset writes from `desktop/` and `ui/`.
- Add-title save paths from desktop and console.

Findings:
- No direct writes to watched dataset/meta JSON from UI add-title code.
- Desktop save path uses `service.save_add_title_record(...)`.
- Console save path uses `service.add_movie(...)`, which routes to `dataset.storage_movie.add_movie(...) -> dataset.dataset_records.add_dataset_record(...)`.

Action:
- No code change in this cycle.

Checks:
- Not rerun; this was a static boundary audit.
