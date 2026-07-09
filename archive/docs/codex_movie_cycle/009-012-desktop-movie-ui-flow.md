# 009-012 Desktop Movie UI Flow

Date: 2026-07-08

Changed:
- Add-title search dialog now has a `Series/Movie` media selector.
- Resolve worker receives and forwards `media_type` to the add-title service layer.
- Preview cards carry `media_type`; preview header shows `Series` or `Movie`.
- Watched cards expose `media_type`; watched list labels show type for explicit typed cards.

Architecture:
- UI still calls `service.resolve_title_for_add()` and `service.save_add_title_record()`.
- UI does not write watched JSON directly.

Checks:
- `py -m compileall common dataset desktop tests\desktop\test_add_title_search_dialog.py tests\desktop\test_watched_media_type_display.py` passed.
- `py -m pytest tests\desktop\test_add_title_search_dialog.py tests\desktop\test_watched_media_type_display.py tests\test_add_title_service.py tests\test_desktop.py::test_format_list_label` passed: `28 passed`.
- `PYTHONDONTWRITEBYTECODE=1 py -m pytest` passed: `788 passed, 1 skipped`.

Visual:
- Native Windows screenshot smoke passed for add-title search dialog.
- Platform plugin: `windows`.
- Font probe: `font_count=355`, `Segoe UI=True`.
- Screenshot: `screens/tmp_ui/movie_add_title_search/search_dialog_movie.png`.
- Observed: no clipped text or widget overlap in the search dialog at current persisted UI scale; country combo arrow area is visually dark but stable.
