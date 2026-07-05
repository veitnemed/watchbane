# Detail Card Hero Contract

This document defines the strict visual and layout contract for the cinematic detail card in the desktop GUI.

## 1. General Layout

- The detail view is one dark cinematic hero card with objectName `detailHeroCard`.
- The top area is a two-column layout:
  - fixed poster column on the left;
  - right info column on the right.
- The right info column order is:
  1. title block: title, then compact title meta;
  2. genre chips;
  3. score summary;
  4. main info panel.
- The overview and additional-info blocks start below the full top row.
- Absolute positioning is forbidden.
- Negative margins are forbidden.
- Fixed right-column height that can clip the main info panel is forbidden.
- If title, chips, score summary, or main info need more height, the layout must grow naturally.

## 2. Poster

- Poster column has a fixed logical poster size around `360x530` before user `ui_scale`.
- Poster is rendered inside a poster shell with rounded corners.
- Poster image uses cover-crop behavior.
- Poster image must never be distorted.
- Poster size is independent from title, chips, score summary, and main info height.
- Missing-poster state must keep the same poster shell size.

## 3. Candidate Actions

- `candidateMarkWatchedButton` and `candidateHideButton` must be under the poster.
- Candidate actions must never appear before the title.
- Candidate actions must never be placed in the score summary row.
- Candidate actions must not change poster size.

## 4. Title Meta

- Title text lives in `detailTitle`.
- Title meta lives in `detailTitleMeta`, directly below the title.
- Title meta format is compact: `2020 • 2 сезона / 20 серий`.
- Missing year or missing seasons/episodes should simply remove that part.
- Title meta must not be duplicated in main info.
- Title meta must not be rendered as chips.

## 5. Chips

- Chip input is genres only.
- Year chips are forbidden.
- Chips may use at most 2 rows.
- A third chip row is forbidden.
- If genres overflow the 2-row limit, show a compact `+N` overflow chip.
- If chips wrap to the second row, score summary, main info, and overview move down through normal layout flow.
- Chips must not overlap title, score summary, main info, or overview.

## 6. Score Summary

- Candidate score row contains:
  - TMDb ring;
  - final_score stars.
- Watched score row contains:
  - TMDb ring;
  - final_score stars.
- A separate "my score" ring is forbidden.
- Score summary must not contain candidate action buttons.
- Score summary must not use raw KP/IMDb rating fields.

## 7. TMDb Ring

- Ring display value is `tmdb_score` formatted to one decimal.
- Ring label is `TMDb`.
- Ring progress is `tmdb_score / 10`.
- Ring color is based on `tmdb_score` progress in the theme cyan/teal palette.
- `final_score` must not affect TMDb ring value, progress, or color.
- The number inside the circle uses the normal text color, not rating yellow.
- Footer text under the ring is forbidden.
- `footer_label` values like `Итог 75` are forbidden.
- If `tmdb_score` is missing, the TMDb ring may be hidden or show an explicit empty state, but it must not use `final_score` as fallback.

## 8. final_score

- `final_score` is visible only as stars.
- Optional qualitative text is allowed, for example `Отличный рейтинг`.
- Raw numeric text like `Итог 75` is forbidden in the hero card.
- Raw percent, raw `final_score`, and hidden debug score text are forbidden.
- final_score stars must not change TMDb ring alignment.

## 9. Watched user_score

- `user_score` is shown only as a poster overlay badge.
- Badge appears in the top-right corner of the poster.
- Badge format is `★ 9.0`.
- Badge is hidden when `user_score` is missing.
- Badge must not affect poster size.
- Badge must not affect right-column layout.
- Do not show `Моя оценка: 9.0` near the title.
- Do not show watched user score as a ring.

## 10. Main Info

- Main info header text is `ОСНОВНАЯ ИНФОРМАЦИЯ`.
- Main info is rendered as a rounded glass panel.
- Rows use `label/value` structure.
- Main info contains type and country.
- Year and seasons/episodes are title meta, not main-info rows.
- TMDb votes live in additional info, not main info.
- Main info must not be clipped after title wraps.
- Main info must not be clipped after chips wrap.
- Main info must not depend on poster height.
- Empty optional values should not create blank rows.

## 11. Overview

- Overview starts below the top row.
- Overview has a divider.
- Overview content starts from the left content edge of the hero card.
- Overview is hidden when overview text is empty.
- Overview must not overlap the poster, right column, or main info panel.
- Overview must grow naturally with wrapped text.

## 12. Additional Info

- Additional info header text is `ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ`.
- Additional info uses the same panel/grid system as main info.
- Rows may include watch providers, status, episode runtime and TMDb votes.
- Empty optional values should not create blank rows.
- Additional info must have a visible top gap from overview content.

## Non-Goals

- This contract does not change runtime data formats.
- This contract does not change TMDb/KP/IMDb migration logic.
- This contract does not change poster-cache download behavior.
- This contract does not change candidate ranking or scoring.
