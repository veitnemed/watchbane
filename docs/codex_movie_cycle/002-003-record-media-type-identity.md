# 002-003 Record Media Type Identity

Date: 2026-07-08

Changed:
- `normalize_main_info()` writes canonical `main_info.media_type`, defaulting legacy payloads to `tv`.
- Dataset identity helpers can compare `title/year/media_type`.
- Add-record validation rejects duplicates only for the same normalized media identity.
- Add-record save builds a suffixed dataset key when the plain title is already used by a different media identity.
- `add_movies_to_meta()` accepts optional `meta_key` so suffixed dataset records do not overwrite existing title meta.

Compatibility:
- Existing callers without `media_type` still save as `tv`.
- Existing duplicate-title checks without year/type keep previous title-only behavior.

Checks:
- `py -m compileall storage dataset tests\dataset\test_record_identity.py tests\dataset\test_records_add.py` passed.
- `py -m pytest tests\dataset\test_media_type.py tests\dataset\test_record_identity.py tests\dataset\test_records_add.py tests\dataset\test_records_validation.py` passed: `35 passed`.
