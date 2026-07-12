# 116 - Russian movie UI filters and duration

## Scope

- Fixed Russian UI strings in movie add/watch flow.
- Added watched-list media type filter: `Всё`, `Сериалы`, `Фильмы`.
- Added movie duration display in detail card through the existing card/model formatting path.
- Kept save/add flow on the existing dataset/service layers; no direct UI JSON writes added.

## Implementation

- Add-title placeholder is now `Введите название`.
- Add-title media selector and preview/list media labels use i18n keys instead of hardcoded `Series`/`Movie`.
- TMDb movie status `Released` is localized to `Выпущен`.
- `United States of America` is normalized through shared country aliases and displays as `США` in Russian mode.
- Movie runtime from `runtime`, `runtime_minutes`, `imdb_runtime_minutes`, including `source_values`, displays as `Продолжительность`.
- Watched filters panel now includes `Тип` combo and model-level filtering by `media_type`.
- Detail main-info header layout was adjusted through `QSizePolicy` to avoid title/toggle overlap at narrower widths.
- Add-title dialog width token was increased to fit title input + media type + country + search controls.

## Verification

- `py -m pytest` -> `804 passed, 1 skipped`.
- TMDb connection smoke: `check_api_available()` returned `ok=True`.
- Real TMDb add-flow smoke:
  - query: `Горничная`, country `US`, `media_type=movie`
  - result: `found=True`, `media_type=movie`, `year=2025`, `runtime=131`, `status=Released`
  - detail rows rendered: `США`, `Выпущен`, `2 ч 11 мин`.

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

- At high UI scale with narrow detail viewport, the existing detail layout uses horizontal scrolling because poster/detail columns have desktop-oriented minimum widths. Scroll works; no new overlap was observed in the checked screenshots.
