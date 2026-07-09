# Current Onboarding Quality Position

Captured on 2026-07-09 from the final mocked onboarding regression run.

Source command:

```text
py scripts/reports/run_onboarding_discover_quality_report.py --mock --all --output reports/onboarding/analysis/final_mock_quality_report.md --json-output reports/onboarding/raw/final_mock_quality_report.json
```

Generated raw/analysis outputs are local ignored artifacts. This file keeps the
small current position that is useful for future comparisons.

## Mocked metrics

| Metric | Current mocked |
| --- | ---: |
| `jp_kr_garbage_rate` | `0.0` |
| `us_gb_new_movies_garbage_rate` | `0.0` |
| `ru_tv_manual_serious_2010_created_count` | `100` |
| `details_requests` | `0` |
| `missing_overview_after_fallback` | `0` |
| `country_hit_rate` | `1.0` |

## Scenario position

- Scenario count: `13`.
- Created total: `1540`.
- Discover requests total: `89`.
- Failed scenarios: none.
- Underfilled scenarios: `ru-tv-manual-serious-2010` at `100/120`.
- Live metrics: `not_run`.
