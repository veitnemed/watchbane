# 108 Hardening TMDb Client Cache

Date: 2026-07-08

Weak spots found:
- Movie search/details had tests, but movie genre cache path was not covered.
- A cache collision or wrong endpoint would affect genre mapping later.

Fixed:
- Added movie genre list test for `/genre/movie/list` and `movie_<language>.json` cache naming.

Checks:
- `py -m compileall apis tests\test_tmdb_api_details.py` passed.
- `py -m pytest tests\test_tmdb_api_details.py` passed: `10 passed`.
