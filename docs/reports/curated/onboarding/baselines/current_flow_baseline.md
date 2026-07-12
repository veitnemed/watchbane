# Current Onboarding Flow Baseline

Step: `001_baseline_current_flow_report`

Scope: reporting only. No production behavior was changed.

## Verified Code Anchors

- Domain flow: `candidates/onboarding/autofill.py`.
- Desktop wizard flow: `desktop/onboarding/wizard.py`.
- Main regression tests: `tests/test_onboarding_autofill.py`.

## Current Wizard Order

1. Setup page: interface language and UI scale.
2. Country selection: multi-select country chips.
3. Media preference: `movie`, `tv`, or `both`.
4. Release preference: `classic`, `new`, or `mixed`.
5. Vibe preference: `light`, `dark`, or `mixed`.
6. Plan review page.
7. Loading/autofill page.
8. Final result page.

## Country, Media, Release, Vibe Behavior

- MVP country picker exposes `US`, `RU`, `GB`, `KR`, `JP`.
- Default selected country is `US`.
- Country payload uses explicit `selected_countries`, equal `country_weights`, `max_countries=5`, and `exclude_home_country=false`.
- `home_country` is `RU` for Russian UI and `US` for English UI.
- Media weights:
  - `movie`: movie-only.
  - `tv`: TV-only.
  - `both`: movie and TV quotas.
- Release ranges:
  - `classic`: 2005-2021.
  - `new`: from 2022 to current date.
  - `mixed`: no lower year bound, current-date upper bound.
- Vibe currently affects quota/scoring metadata only. It is not a hard Discover filter unless explicit include genres are supplied.

## Current Discover Contract

- Endpoint:
  - movies: `/discover/movie`;
  - TV: `/discover/tv`.
- Country-first behavior:
  - every generated bucket has `target_country`;
  - Discover params include `with_origin_country=<selected country>`;
  - hard-origin buckets do not use broad-origin fallback by default.
- Initial Discover params:
  - `include_adult=false`;
  - `language` derived from UI language (`ru-RU` or `en-US`);
  - `sort_by=popularity.desc`;
  - `page=request_index + 1`;
  - date upper bound is always capped to current date;
  - no `vote_count.gte`;
  - no `vote_average.gte`.
- Genre behavior:
  - explicit include genres are joined with `|` by default;
  - explicit `include_genre_mode="and"` joins with `,`;
  - TV Discover excludes junk genres by default: `10766,10764,10767,10763,10762,99`.
- Page limits:
  - `DEFAULT_DISCOVER_PAGES=3`;
  - `MAX_DISCOVER_PAGES=5`;
  - current runtime loop uses the max of configured pages and max pages, so the effective ceiling is currently at least 5.
- Details:
  - current starter flow is Discover-result based;
  - there is no selective Details enrichment stage in this baseline.

## Known Missing Pieces Versus Target Plan

- `TastePreset` domain contract is not present.
- `animation_mode` domain/UI contract is not present.
- Selective Details enrichment is not implemented.
- Localization overview fallback for candidate quality is not implemented as a dedicated onboarding step.
- Candidate Quality Gate v1 is not implemented.
- Adaptive pagination is not integrated.
- Timeout/retry/outlier diagnostics are limited.
- Expanded report metrics schema is not present.

## Targeted Test Command

```powershell
py -m compileall candidates desktop tests
py -m pytest tests/test_onboarding_autofill.py -q
```

Captured output: `reports/onboarding/raw/current_flow_test_log.txt`.

## Baseline Metrics Placeholders

These placeholders are intentionally empty until later measurement steps add data.

| Metric | Baseline value | Notes |
| --- | ---: | --- |
| JP garbage_rate | TBD | Requires acceptance scenario/reporting step. |
| KR garbage_rate | TBD | Requires acceptance scenario/reporting step. |
| US new movies garbage_rate | TBD | Requires acceptance scenario/reporting step. |
| GB new movies garbage_rate | TBD | Requires acceptance scenario/reporting step. |
| `ru-tv-manual-serious-2010` created count | TBD | Requires scenario fixture. |
| details_requests | 0 | No selective Details stage in current baseline. |
| missing_overview_after_fallback | TBD | Fallback is not implemented yet. |
| country hit rate | TBD | Needs report metrics schema. |

## Baseline Risks

- Country-first contract is guarded by tests, but current quality depends on raw Discover output quality.
- No Details pass means weak overview/localization/completeness data can remain in starter candidates.
- There is no explicit quality gate, so low-signal Discover results can pass if they satisfy existing structural filters.
