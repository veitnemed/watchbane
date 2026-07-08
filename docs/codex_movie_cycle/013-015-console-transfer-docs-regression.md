# 013-015 Console, Transfer, Docs And Regression

Date: 2026-07-08

Changed:
- Console add-title flow asks for `Series/Movie` and forwards `media_type` to resolve.
- Manual console fallback preserves requested media type.
- Candidate transfer preserves candidate `media_type` and can derive movie year from `release_date`.
- README documents TV/Movie add-title flow.
- Add-record rules document `main_info.media_type`, service-path save and duplicate policy by `title/year/media_type`.

Checks:
- `py -m compileall ui dataset tests\test_console_request_tmdb_only.py tests\dataset\test_candidate_transfer.py` passed.
- `py -m pytest tests\test_console_request_tmdb_only.py tests\dataset\test_candidate_transfer.py tests\test_add_title_service.py` passed: `32 passed`.
- `py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests` passed.
- `PYTHONDONTWRITEBYTECODE=1 py -m pytest` passed: `791 passed, 1 skipped`.
