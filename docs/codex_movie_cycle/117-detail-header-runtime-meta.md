# 117 - Detail header and movie runtime meta

## Scope

- Fix the detail main-info header so `ОСНОВНАЯ ИНФОРМАЦИЯ` is not cut by the `Показать больше` / `Скрыть` button.
- Move movie runtime out of the main-info rows and into the title meta line next to the year.
- Recheck the Russian movie UI screenshots for similar clipped-text issues.

## Implementation

- Main-info header now uses a vertical layout: title on its own row, toggle button below it.
- The toggle button is left-aligned in the second row, with the divider filling the remaining width, so narrow visible areas show the title and action first.
- Movie title meta now formats runtime as `2025 • 2 ч 15 мин` when movie runtime is available.
- Movie runtime is no longer emitted as a separate `Продолжительность` row in main info.

## Verification

- `py -m pytest tests/desktop/test_detail_movie_info.py tests/test_desktop.py::test_build_title_meta_text_formats_year_and_seasons tests/test_desktop.py::test_build_title_meta_text_formats_movie_runtime_next_to_year tests/test_desktop.py::test_detail_main_info_header_does_not_share_row_with_toggle tests/test_desktop.py::test_detail_main_info_toggle_collapses_and_expands_rows tests/test_ui_scale_settings.py::test_hardcoded_px_guard_for_direct_sizing_calls -q` -> `9 passed`.
- `py -m pytest` -> `807 passed, 1 skipped`.

## Screenshots

Native Windows screenshots, `QT_QPA_PLATFORM=windows`.

- Font probe: `font_count=355`, `Segoe UI=True`.
- `screens/tmp_ui/movie_ui_checks/add_title_search_scale100.png`
- `screens/tmp_ui/movie_ui_checks/add_title_search_scale125_wide.png`
- `screens/tmp_ui/movie_ui_checks/watched_media_filter_scale100.png`
- `screens/tmp_ui/movie_ui_checks/watched_media_filter_expanded_scale100.png`
- `screens/tmp_ui/movie_ui_checks/watched_media_filter_expanded_scrolled_scale100.png`
- `screens/tmp_ui/movie_ui_checks/watched_media_filter_scale125_wide.png`

## Notes

- Checked collapsed, expanded and expanded-scrolled main-info states. Header text is no longer clipped by the toggle button.
- Runtime is visible in the title meta line as `2025 • 2 ч 11 мин` for the checked movie card.
- At 125% scale, the existing detail view still relies on horizontal scrolling because the poster/detail desktop columns are wider than the visible area. This is a separate responsive-layout issue; this change keeps the header and toggle readable within that layout.
