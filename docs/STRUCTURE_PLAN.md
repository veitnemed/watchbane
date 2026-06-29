# Structure Plan

Goal

- Make `series-list` a clean, non-legacy local series search project structure.

Done

- `model/` moved to `archive/legacy/model/`.
- legacy root `tests/` moved to `archive/legacy/tests/`.
- active tests now live in `tests/`.
- restored read-only `web/` layer for watched/add-title card behavior.
- standalone scripts moved to `scripts/`: `build_candidate_pool.py`, `evaluate_candidate_pool.py`.
- `desktop_image/` moved to `assets/desktop/`.

Current structure

- `app/`, `dataset/`, `candidates/`, `desktop/`, `posters/`, `ui/`, `storage/`, `config/`, `common/`, `apis/` are active runtime packages.
- `datasets/` holds local IMDb SQLite resources and builder scripts.
- `data/` is runtime drafts/cache.
- `reports/` stores historical script reports.
- `scripts/` contains diagnostic/build utilities.

Next transfers

- decide whether to convert runtime imports and module layout to a package namespace `series_list/`.
