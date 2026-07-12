# Onboarding Implementation Final Report Template

Use this template for branch review after the onboarding quality-gate work.
Do not fabricate live metrics. Use `not_captured` when a baseline or current
run was not captured.

## Changed files

- `<path>` - `<short reason>`.

## Discover filter confirmation

- Initial Discover requests do not include `vote_count.gte`.
- Initial Discover requests do not include `vote_average.gte`.
- Vote count and rating are used only after Discover for confidence, scoring,
  quality classification and ranking.

## Vote confidence scoring formula

`rating_bonus_adjusted = vote_average * 100 * vote_confidence`

`vote_confidence_for_count(vote_count)`:

| Vote count | Confidence |
| ---: | ---: |
| `<= 0` | `0.15` |
| `1..5` | `0.25` |
| `6..20` | `0.45` |
| `21..50` | `0.65` |
| `51..100` | `0.80` |
| `101..299` | `0.90` |
| `>= 300` | `1.00` |

## Details enrichment behavior

- Discover results are deduped before Details.
- Details enrichment is selective and bounded by the per-bucket cap.
- Details may fetch external IDs when configured.
- Enriched fields are merged back into the Discover candidate before final
  score and quality classification are recalculated.
- TV season data remains lazy on card open unless explicitly enabled.

## Localization fallback behavior

- Candidates with a UI-language overview are marked `ui_language`.
- Missing overviews try original-language Details when available.
- Missing overviews can then try `en-US`.
- Candidates still missing an overview are marked `missing` and counted in
  `missing_overview_after_fallback`.

## Quality gate rules

Garbage candidates are blocked from normal onboarding pool insertion. Typical
garbage reasons:

- wrong selected country;
- wrong media type;
- starter TV junk genre;
- missing poster plus missing overview;
- missing overview with very low vote/popularity confidence;
- suspicious adult-like title when TMDb does not mark the row as adult;
- duplicate-like candidate;
- emergency fallback outside selected countries;
- no useful metadata.

Weak candidates remain eligible when metadata is still useful. Typical weak
reasons:

- low votes;
- fallback overview;
- rating `0`;
- very new title with little metadata;
- missing external ID;
- low popularity.

Good candidates have no garbage or weak reasons.

## Adaptive pagination rules

- Each bucket can run the default page window.
- After the default window, low accepted yield stops the bucket.
- Useful yield can continue through the normal max page cap.
- Underfilled high-yield selected-country buckets can continue to the adaptive
  max page cap before any fallback path is considered.
- Stop reasons are reported in `pagination_stop_reasons`.

## Tests run

```text
py -m compileall candidates desktop tests
py -m pytest tests/test_onboarding_autofill.py -q
```

Add any extra targeted tests that were run for the branch.

## Before/after metrics

| Metric | Baseline | Current | Delta |
| --- | ---: | ---: | ---: |
| `jp_kr_garbage_rate` | `not_captured` | `not_captured` | `not_captured` |
| `us_gb_new_movies_garbage_rate` | `not_captured` | `not_captured` | `not_captured` |
| `ru_tv_manual_serious_2010_created_count` | `not_captured` | `not_captured` | `not_captured` |
| `details_requests` | `not_captured` | `not_captured` | `not_captured` |
| `missing_overview_after_fallback` | `not_captured` | `not_captured` | `not_captured` |
| `country_hit_rate` | `not_captured` | `not_captured` | `not_captured` |

## Before/after onboarding scenario output

- Baseline scenario report: `not_captured`.
- Current scenario report: `not_captured`.
- Failed scenarios: `not_captured`.
- Notes: `not_captured`.
