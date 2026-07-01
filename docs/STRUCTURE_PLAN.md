# Structure Plan

Goal

- Make `watchbane` a clean, non-legacy local series search project structure.

Done

- `model/` moved to `archive/legacy/model/`.
- legacy root `tests/` moved to `archive/legacy/tests/`.
- active tests now live in `tests/`.
- restored read-only `web/` layer for watched/add-title card behavior.
- standalone scripts moved to `scripts/`: `build_candidate_pool.py`, `evaluate_candidate_pool.py`.
- `desktop_image/` moved to `assets/desktop/`.
- `candidates.service` public wrappers are covered against self-recursion.
- watched poster cache reload test uses the active `desktop.watched.model.load` module.
- API ping console action moved from `interface_funcs.py` to `ui/console/api_tools.py` with a compatibility import.
- Local SQL search console action moved from `interface_funcs.py` to `ui/console/sql_tools.py` with compatibility imports.
- Watched metadata/poster maintenance actions moved from `interface_funcs.py` to `ui/console/poster_tools.py`.
- Candidate pool maintenance and diagnostics moved from `interface_funcs.py` to `ui/console/candidate_pool_tools.py`.
- TMDb candidate pool build/import flow moved from `interface_funcs.py` to `ui/console/tmdb_pool_tools.py`.
- Console navigation is now maintenance-first: `maintenance_menu`, `watched_menu`, `pool_menu`, `search_hub_menu`, and `reference_menu` own the top-level sections.
- `storage.runtime.ensure_runtime_data_layout()` centralizes runtime directory and JSON initialization.
- [REFACTORING_CHECKLIST.md](REFACTORING_CHECKLIST.md) documents the required checks for structural changes.

Current structure

- `app/`, `dataset/`, `candidates/`, `desktop/`, `posters/`, `ui/`, `storage/`, `config/`, `common/`, `apis/` are active runtime packages.
- `datasets/` holds local IMDb SQLite resources and builder scripts.
- `data/` is runtime drafts/cache.
- `scripts/` contains diagnostic/build utilities.

Next transfers

- Move remaining watched actions from `ui/console/interface_funcs.py` into `ui/console/watched_tools.py`.
- Move remaining domain-layer `print()`/`input()` behavior into UI or `scripts/` wrappers.
- Extend `storage.runtime` into a migration/check layer for invalid runtime JSON structures.
- Decide later whether to convert runtime imports and module layout to a package namespace `series_list/`.
