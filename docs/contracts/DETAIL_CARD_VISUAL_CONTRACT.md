# Watchbane Detail Card Visual Contract

Status: strict UI contract for `desktop/shared/detail/*` and related desktop tests.

This contract exists because the detail card has already drifted through several incompatible states. Future agents must treat this file as the source of truth before changing the card layout, score rings, stars, or candidate actions.

## 1. Scope

This contract applies to the PyQt detail card used by:

- watched library detail view;
- candidate detail/preview view;
- add-title preview when it reuses the same shared detail-card components.

It does not authorize changes to dataset JSON formats, candidate pool JSON formats, TMDb API flows, poster cache storage, scoring formulas, metadata refresh scripts, console flows, or files under `archive/legacy/`.

## 2. Main visual model

The card has one fixed poster column and one flexible information column.

```text
[ poster column ]   [ information column ]
[ poster        ]   [ title                ]
[ candidate     ]   [ title meta           ]
[ actions only  ]   [ genre pills           ]
                  [ TMDb ring + stars     ]
                  [ main information     ]

[ overview full-width below both columns ]
[ additional information below overview ]
```

The title row must contain only the title. Title meta (`year • seasons / episodes`) is a compact line directly below the title. Candidate actions must never be placed before the title or inside the title row.

## 3. Rating and score semantics

The detail card has three separate visual signals. They must not be merged.

| Visual element | Source field | Meaning | Allowed display |
| --- | --- | --- | --- |
| TMDb circle | `tmdb_score` | External public TMDb rating, 0..10 | Number inside circle, label `TMDb`, ring progress, cyan/teal ring color |
| User score badge | `user_score` | User's own rating, 0..10 | Poster overlay badge `★ 9.0` only |
| Final stars | `final_score` | Internal recommendation/result score | 1..5 star scale only, no numeric `Итог 75` text |

Hard rule: `final_score` must never control TMDb circle progress, TMDb circle color, or the number inside the TMDb circle.

Hard rule: `tmdb_score` must never be described as `Итог`.

Hard rule: `quality_score` is an internal scoring signal and must not appear in this detail card unless a future task explicitly asks for a diagnostics/debug view.

## 4. TMDb circle contract

The TMDb circle is the public-rating circle.

Required behavior:

- display value: formatted `tmdb_score` with one decimal, or `—` when absent;
- label: exactly `TMDb`;
- progress: `clamp(float(tmdb_score) / 10, 0, 1)`, or `0` when absent/invalid;
- color: derived from `tmdb_score`, not from `final_score`, using the current cyan/teal theme range;
- value color: normal text color, not rating yellow;
- footer text: none;
- watched user score must not appear as a second ring.

Regression examples:

```python
card = {"tmdb_score": 8.0, "final_score": 0.20}
# TMDb circle must look strong: progress 0.80, cyan/teal high-score color.
# It must not look like 20%.

card = {"tmdb_score": 4.0, "final_score": 0.90}
# TMDb circle must look weak/medium by TMDb: progress 0.40.
# It must not change because final_score is high.
```

## 5. User score badge contract

The user's score is a poster overlay badge, not a circle.

Required behavior:

- display value: formatted `user_score` with one decimal;
- text format: `★ 9.0`;
- location: top-right poster overlay;
- missing/invalid value: hide badge;
- badge must not affect poster size;
- badge must not affect right-column layout.

Showing watched user score as a circle, title-row text, main-info row, or score-summary item is forbidden.

## 6. Final score stars contract

`final_score` is shown as stars, not as a number under a circle.

Required behavior:

- source: `final_score` only;
- accepted source scale: either `0..1` or `0..100`;
- normalization: values above `1` are treated as percent and divided by `100`;
- visual scale: 1..5 stars, half-star steps are allowed;
- missing/invalid value: hide the stars or show a quiet placeholder, but reserve enough vertical space to keep the circles aligned;
- no text `Итог 75`, `Итог —`, `final_score`, or raw percent below the circles;
- stars are a separate widget/row, not a footer inside `RatingCircleIndicator`.
- the label above the stars in the watched film/series card is exactly `WatchBane`.

Suggested mapping:

```python
normalized = normalize_final_score(final_score)  # 0..1
stars = round(normalized * 10) / 2               # half-star scale
stars = max(1.0, min(5.0, stars))                # 1..5 when present
```

Examples:

```python
final_score = 0.74  # 3.5 or 4.0 stars depending on rounding policy, but never text "Итог 74".
final_score = 86    # normalized to 0.86, shown as stars only.
```

The star widget must not widen either rating circle slot. It must not move the TMDb circle horizontally.

## 7. Rating block layout

The rating block has a TMDb ring slot and final-score stars:

```text
[ fixed TMDb slot ][ gap ][ final-score stars ]
```

Required layout behavior:

- TMDb ring keeps a fixed slot;
- final-score stars are a separate widget next to the ring;
- final-score stars keep a fixed horizontal gap from the TMDb slot when main information is collapsed or expanded;
- star width must not affect TMDb ring value/progress;
- missing stars must not make the ring jump vertically;
- candidate actions never enter this score row.

Forbidden implementation patterns:

- adding star text as `footer_label` in `RatingCircleIndicator`;
- putting stars inside the TMDb circle widget;
- increasing the TMDb widget width to fit stars;
- using a temporary `tuning.py` module as the final committed state.

## 8. Candidate action buttons

Candidate actions are poster actions, not title actions.

Required behavior:

- buttons `candidateMarkWatchedButton` and `candidateHideButton` appear only when the candidate profile enables them;
- they are placed under the poster in the poster column;
- they are centered or left-aligned consistently under the poster, not before the title;
- title row remains stable and starts with the title label;
- watched view does not show these buttons.

Button size may stay at the current compact size, but the row must be visually separate from the title.

## 9. Main information and overview

The detail card must not sacrifice content to keep the top row the same height as the poster.

Required behavior:

- `Основная информация` remains visible when it has items;
- long values wrap instead of clipping;
- the information column must not have a maximum height equal to the poster height;
- overview is a full-width block below the top poster/info row;
- empty overview hides the overview block.

## 10. Film/series media badge

The poster media-type badge is a solid pill over the poster, not translucent text.

Required behavior:

- text: localized uppercase `ФИЛЬМ` or `СЕРИАЛ`;
- location: bottom-center poster overlay;
- fill: opaque dark film palette fill, with the series variant using the series badge background token;
- border: cyan/series border token from the film palette;
- text color: film/series badge text token;
- it must remain readable over bright and dark poster artwork at 75%, 100%, and 150% UI scale.

Main information rows:

- `Тип` from normalized `object_type` or TV-shape fallback;
- `Страна` from `country` when present;
- `Где смотреть` from watch providers, or `нет данных` when absent;
- `Голоса TMDb` from `tmdb_votes` when positive.

Title meta:

- `Год` is shown under title, not in main information;
- `Сезоны / серии` is shown under title, not in main information.

Additional information rows:

- status;
- episode runtime.

## 10. Code ownership boundaries

Expected files for UI changes:

- `desktop/shared/detail/card.py` — layout structure and widget placement;
- `desktop/shared/detail/rating_indicator.py` — circular rating widget only;
- `desktop/shared/detail/card_pills.py` — creation/filling helpers for rating/meta widgets;
- `desktop/shared/detail/presenters.py` — pure formatting/payload builders;
- `desktop/shared/detail/profiles.py` — sizing constants/profile values;
- `desktop/theme/*` — shared visual tokens, only when truly needed;
- `tests/test_desktop.py` and/or `tests/desktop/*` — regression tests for contract behavior.

Do not change scoring formulas to satisfy a visual request. The visual layer consumes score fields; it does not redefine them.

## 11. Required regression tests

At minimum, tests must cover these cases:

```python
def test_tmdb_ring_uses_tmdb_score_not_final_score():
    item = build_score_ring_item({"tmdb_score": 8.0, "final_score": 0.20})
    assert item["display_value"] == "8.0"
    assert item["display_label"] == "TMDb"
    assert item["ring_progress"] == 0.80
    assert item.get("footer_label") in (None, "")


def test_tmdb_ring_color_uses_tmdb_score_not_final_score():
    high_tmdb_low_final = build_score_ring_item({"tmdb_score": 8.0, "final_score": 0.20})
    low_tmdb_high_final = build_score_ring_item({"tmdb_score": 4.0, "final_score": 0.90})
    assert high_tmdb_low_final["accent"] != low_tmdb_high_final["accent"]


def test_final_score_is_stars_not_ring_footer():
    tmdb_item = build_score_ring_item({"tmdb_score": 7.4, "final_score": 0.74})
    stars_item = build_final_score_star_item({"final_score": 0.74})
    assert tmdb_item.get("footer_label") in (None, "")
    assert stars_item is not None
    assert stars_item["kind"] == "final_stars"


def test_watched_user_score_is_badge_not_ring(qapp):
    # user_score must be rendered as detailUserScoreBadge only.
    # It must not create a second score ring in the score summary row.
    ...


def test_title_meta_is_under_title_not_main_info(qapp):
    # year and seasons/episodes must live in detailTitleMeta.
    # Main information must not duplicate them as rows.
    ...


def test_candidate_actions_are_not_in_title_row(qapp):
    # candidateMarkWatchedButton and candidateHideButton must be descendants
    # of the poster/actions column, not of detailTitleActions/title row.
    ...
```

If existing tests still assert `ring_progress == final_score` or `footer_label == "Итог 74"`, those tests are preserving the old bug and must be rewritten.

## 12. Agent instructions for future UI work

Before changing the detail card, an agent must state which invariant it is touching and which invariants it will not touch.

Allowed response shape for an implementation task:

1. Identify current contract violations.
2. Change the smallest number of files.
3. Update tests so they assert the contract, not the previous bug.
4. Run `py -m compileall desktop tests` and the relevant desktop tests.
5. Report exact files changed and exact contract checks satisfied.

The agent must stop and explain before making any change that would affect data formats, scoring formulas, TMDb refresh behavior, or poster cache behavior.
