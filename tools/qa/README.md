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
