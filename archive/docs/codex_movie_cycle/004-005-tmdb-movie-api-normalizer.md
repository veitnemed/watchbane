# 004-005 TMDb Movie API And Normalizer

Date: 2026-07-08

Changed:
- Added TMDb movie search helper for `/search/movie`.
- Added TMDb movie details helper for `/movie/{id}` with movie-specific append defaults.
- Added movie genre list helper for `/genre/movie/list`.
- Added `normalize_tmdb_movie()` with movie fields: `media_type`, `release_date`, `runtime`, movie certification, credits, ratings, posters, countries and genres.

Compatibility:
- Existing TV helpers and TV detail append defaults are unchanged.
- Movie details cache keys are prefixed with `movie_` to avoid collisions with TV details.

Checks:
- `py -m compileall apis tests\test_tmdb_api_details.py` passed.
- `py -m pytest tests\test_tmdb_api_details.py` passed: `9 passed`.
