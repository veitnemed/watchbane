# Safe isolated recommendation QA launcher (C3-06)

Prevents **QA-DEFECT-03**: importing Watchbane before `WATCHBANE_DATA_DIR` freezes
`config.constant.APP_DATA_DIR` onto the real user profile.

## Command

From the repo root:

```powershell
py -m tools.qa.run_recommendation_audit --runtime-root tmp/qa_runtime_c306
```

Or:

```powershell
py tools/qa/run_recommendation_audit.py --runtime-root D:\path\to\isolated_runtime
```

`--runtime-root` is **required**. There is no silent fallback to `%LOCALAPPDATA%\Watchbane`.

## What it does

1. Resolves and validates the runtime root (rejects real APPDATA / parents / nested paths).
2. Sets `WATCHBANE_DATA_DIR` in the parent (parent never imports `config.constant`).
3. Writes `.watchbane_qa_isolated` + evidence JSON.
4. Spawns a child that imports `config.constant` and proves `APP_DATA_DIR` is inside the runtime.
5. Exits non-zero before any audit child work if isolation fails.

## Notes

- Does **not** clean possible prior contamination of the real profile.
- Does **not** fix adult/safety (QA-DEFECT-01) or localization (QA-DEFECT-02).
- Ad-hoc scripts under `screens/tmp_ui/C3-05/` are not the supported entrypoint.

## C3-10: synthetic taste-profile evaluation

The deterministic QA-only harness uses three strict JSON profiles, a fixed
offline pool and synthetic watched/saved/hidden history. It calls the existing
recommendation deck service; it does not alter product ranking or click the UI.

```powershell
py -m tools.qa.run_synthetic_taste_profile_evaluation `
  --runtime-root screens/tmp_ui/C3-10/runtime `
  --output-dir screens/tmp_ui/C3-10
```

The command writes one report per profile plus `child_isolation_proof.json`.
Unknown profile fields are validation errors. Keyword/franchise constraints
without a current filter-contract equivalent are recorded as audit-only checks,
never implemented as a parallel filter.

## C3-11: vibe-alignment audit

Each synthetic profile also declares an audit-only `vibe_alignment` rubric.
The report records per-card mismatch reasons and deck-level thresholds for
matching cards plus distinct countries and genres. It evaluates metadata after
the production deck is built; it never changes product filtering or ranking.

For example, a "heavy Russian drama" rubric can require `RU` and `drama`, and
forbid `school` or `fan service` keywords. A returned school drama is then a
visible mismatch in the JSON report rather than a hidden post-filter.

## C3-12: output-defect audit

Run the isolated combined audit with:

```powershell
py -m tools.qa.run_output_defect_audit `
  --runtime-root screens/tmp_ui/C3-12/runtime `
  --output-dir screens/tmp_ui/C3-12
```

It writes `output_defect_audit.json`. All current onboarding `PRESETS` are
checked through the existing fetch/discover builders (including
`include_adult=False`); synthetic top-10 cards are checked for placeholders,
mojibake, missing visible metadata, and explicit/hentai/porn signals from
title, overview and keywords using the existing safety gate. It is offline and
does not prove live TMDb availability.
