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
- Shared isolation helpers live in `tools/qa/isolation.py`.
- Synthetic taste profiles P1–P3 and their runners were removed after C3-10…C3-12;
  use `tests/helpers/candidate_factory.py` for technical fixtures instead.
- TMDb product contract: [`docs/research/tmdb_data_contract.md`](../../docs/research/tmdb_data_contract.md).
