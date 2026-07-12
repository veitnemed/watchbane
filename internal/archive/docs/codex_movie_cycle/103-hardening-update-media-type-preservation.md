# 103 Hardening Update Media Type Preservation

Date: 2026-07-08

Weak spots found:
- Add/update paths now normalize `main_info.media_type`, but update had no focused regression test proving the field survives score edits.
- Losing `media_type` during update would break movie identity/display after later edits.

Fixed:
- Added regression coverage for `update_dataset_record()` preserving `main_info.media_type`.

Checks:
- `py -m compileall dataset\records tests\dataset\test_records_update.py` passed.
- `py -m pytest tests\dataset\test_records_update.py` passed: `4 passed`.
