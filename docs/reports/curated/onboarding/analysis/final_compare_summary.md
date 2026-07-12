# Final Onboarding Compare Summary

Generated on 2026-07-09 from the final mocked onboarding regression run.

## Changed systems

- Starter onboarding taste presets and preset-card wizard flow.
- Country-first Discover planning with explicit guardrails against initial
  `vote_count.gte` and `vote_average.gte` filters.
- Low-vote confidence scoring after Discover.
- Selective Details enrichment hooks, overview localization fallback and
  details/localization metrics.
- Candidate Quality Gate v1 with `garbage`, `weak` and `good` classes.
- Adaptive pagination for high-yield underfilled country-first buckets.
- Report hygiene, before/after compare helper and final report template.
- Small module boundary cleanup for Details and Pagination config contracts.

## Tests and regression run

```text
py scripts/reports/run_onboarding_discover_quality_report.py --mock --all --output reports/onboarding/analysis/final_mock_quality_report.md --json-output reports/onboarding/raw/final_mock_quality_report.json
py -m compileall candidates desktop tests
py -m pytest tests/test_onboarding_autofill.py -q
py -m pytest tests/candidate_modules tests/test_runtime_reports.py -q
```

Results:

- Mocked scenario count: `13`.
- Mocked created total: `1540`.
- Mocked Discover requests total: `89`.
- Full 120/120 pools: `12` of `13`.
- Underfilled scenario: `ru-tv-manual-serious-2010` at `100/120`.
- Failed mocked scenarios: none.
- Live metrics: `not_run`.

## Current mocked before/after metrics

Baseline sources:

- Historical scenario quality report:
  `docs/reports/onboarding/onboarding_country_first_10_scenario_quality_report.md`.
- Initial flow baseline for pre-Details request count:
  `reports/onboarding/baselines/current_flow_baseline.md`.

Current source:

- Local generated JSON:
  `reports/onboarding/raw/final_mock_quality_report.json`.

| Metric | Baseline | Current mocked | Delta |
| --- | ---: | ---: | ---: |
| `jp_kr_garbage_rate` | `0.3917` | `0.0` | `-0.3917` |
| `us_gb_new_movies_garbage_rate` | `0.2417` | `0.0` | `-0.2417` |
| `ru_tv_manual_serious_2010_created_count` | `82` | `100` | `+18` |
| `details_requests` | `0` | `0` | `0` |
| `missing_overview_after_fallback` | `not_captured` | `0` | `not_captured` |
| `country_hit_rate` | `1.0` | `1.0` | `0` |

## Current mocked scenario output

All 13 mocked scenarios completed successfully with `country_hit_rate = 1.0`
and `garbage_rate = 0.0`.

The only remaining mocked underfill is `ru-tv-manual-serious-2010`, now
`100/120` versus the historical `82/120`. This scenario remains intentionally
country-first and does not fall back outside the selected country to fill the
pool.

## Known risks

- Live TMDb metrics were not run in this final cleanup step: `not_run`.
- The final mocked run did not exercise live Details/localization API behavior;
  current mocked `details_requests` is `0`.
- The narrow RU TV serious/classic scenario can still underfill, although the
  final mocked position improved from `82` to `100`.

## Next validation

Run live validation when credentials and quota are available:

```text
py scripts/reports/run_onboarding_discover_quality_report.py --live --all --require-live --output reports/onboarding/analysis/live_quality_report.md --json-output reports/onboarding/raw/live_quality_report.json
```

Manually inspect `ru-tv-manual-serious-2010`, `ru-manual-jp-kr` and
`ru-foreign-new-movies-us-gb` in the live output before merging.
