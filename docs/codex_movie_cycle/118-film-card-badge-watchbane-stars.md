# 118 - Film card badge and WatchBane stars

## Scope

- Make the poster media-type badge (`ФИЛЬМ` / `СЕРИАЛ`) opaque and readable over different posters.
- Rename the watched final-score stars label from `Моя оценка` to `WatchBane`.
- Fix the star-row drift when the main-info section is expanded.
- Recheck the film/series detail card at 75%, 100%, and 150% UI scale.

## Implementation

- Added a custom-painted media-type badge label so the pill fill and border are always opaque and use the film palette tokens.
- Kept QSS responsible for badge text metrics and color, while custom paint owns the solid pill background.
- Changed the final-score stars label to `WatchBane`.
- Reworked the score summary row so stars keep a fixed gap from the TMDb ring instead of depending on stretch centering.
- Fixed the main-info toggle width for both collapsed and expanded labels.
- Bounded main-info value width from the detail-card profile to avoid expanded values pushing the score row.
- Extended `scripts/capture_film_card.py` with `--match-index` and `--expand-main-info` for repeatable title and expanded-state screenshots.

## Verification

- `py -m compileall desktop tests scripts` -> passed.
- `py -m pytest` -> `893 passed, 1 skipped`.
- Native Windows screenshots, `QT_QPA_PLATFORM=windows`.
- Font probe: `family_count=355`, `Segoe UI=True`, `Arial=True`.

## Screenshots

- `screens/tmp_ui/film_card/fix_badge_stars_movie0_scale075.png`
- `screens/tmp_ui/film_card/fix_badge_stars_movie0_scale100.png`
- `screens/tmp_ui/film_card/fix_badge_stars_movie0_scale100_expanded.png`
- `screens/tmp_ui/film_card/fix_badge_stars_movie0_scale150_scrolled.png`
- `screens/tmp_ui/film_card/fix_badge_stars_tv0_scale075.png`
- `screens/tmp_ui/film_card/fix_badge_stars_tv0_scale100.png`
- `screens/tmp_ui/film_card/fix_badge_stars_tv0_scale100_expanded.png`
- `screens/tmp_ui/film_card/fix_badge_stars_tv0_scale150_scrolled.png`
- `screens/tmp_ui/film_card/fix_badge_stars_tv1_scale100.png`

## Notes

- Checked `Горничная`, `Игра на выживание`, and `Чернобыль: Зона отчуждения`.
- At 150% scale the existing detail surface still needs horizontal scrolling. The stars and `WatchBane` label remain stable inside that layout, but reducing horizontal scroll is a separate responsive-layout task.
