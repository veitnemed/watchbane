# 006-008 Resolve And Save Movie Path

Date: 2026-07-08

Changed:
- Add-title defaults include `main_info.media_type`, defaulting to `tv`.
- TMDb resolve can run with `media_type="movie"` and uses movie search/details/normalizer.
- Movie resolve stores movie-specific defaults and source values.
- Add-title bundle fallback defaults preserve requested media type.
- Save path preserves movie media type through `dataset.storage_movie.add_movie(...)`.

Compatibility:
- Public add-title resolve remains TV by default.
- Existing TV resolve tests continue using TV append defaults.

Checks:
- `py -m compileall apis dataset tests\dataset\test_resolve_sources_tmdb_only.py tests\dataset\test_resolve_service.py tests\test_add_title_service.py` passed.
- `py -m pytest tests\dataset\test_resolve_sources_tmdb_only.py tests\dataset\test_resolve_service.py tests\test_add_title_service.py tests\dataset\test_records_add.py` passed: `31 passed`.
