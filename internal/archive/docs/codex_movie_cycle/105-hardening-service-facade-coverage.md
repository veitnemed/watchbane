# 105 Hardening Service Facade Coverage

Date: 2026-07-08

Weak spots found:
- Movie resolve was covered at internal resolve modules, but not through the public `dataset.service` facade used by UI clients.
- Facade regressions would be easy to miss if imports changed.

Fixed:
- Added facade-level regression for `resolve_title_data_for_add(..., media_type="movie")`.

Checks:
- `py -m compileall dataset tests\dataset\test_service_facade.py` passed.
- `py -m pytest tests\dataset\test_service_facade.py` passed: `5 passed`.
