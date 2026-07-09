# 001 Media Type Contract

Date: 2026-07-08

Changed:
- Added `dataset.models.media_type` with canonical values `tv` and `movie`.
- Added normalization helpers and predicates.
- Added unit tests for legacy defaults, aliases, and predicates.

Compatibility:
- Missing, empty, and unknown media types normalize to `tv`.
- Existing TV-only records keep their effective behavior.

Checks:
- `py -m compileall dataset tests\dataset\test_media_type.py` passed.
- `py -m pytest tests\dataset\test_media_type.py` passed: `19 passed`.
