# 109 Hardening Read Model Display

Date: 2026-07-08

Weak spots found:
- Watched display labels exposed explicit media type, but search haystack did not include it.
- Typed entries should remain searchable by their type label/key.

Fixed:
- Added `main_info.media_type` and record-level `media_type` to watched search haystack.
- Added regression coverage.

Checks:
- `py -m compileall desktop\watched\model tests\desktop\test_watched_media_type_display.py` passed.
- `py -m pytest tests\desktop\test_watched_media_type_display.py tests\desktop\test_watched_search_behavior.py` passed: `4 passed`.
