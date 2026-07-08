# 102 Hardening Worker TypeError Fallback

Date: 2026-07-08

Weak spots found:
- Worker fallback for old test doubles caught any `TypeError`, including real service bugs.
- Existing compatibility test still needs old callables without `media_type`.

Fixed:
- Worker now checks callable signature before deciding whether to pass `media_type`.
- Internal service `TypeError` is no longer masked as a compatibility fallback.

Checks:
- `py -m compileall desktop\watched\add_title\worker.py tests\test_desktop.py` passed.
- `py -m pytest tests\test_desktop.py::test_add_title_worker_passes_data_language tests\test_desktop.py::test_add_title_worker_does_not_mask_service_type_error tests\desktop\test_add_title_search_dialog.py` passed: `12 passed`.
