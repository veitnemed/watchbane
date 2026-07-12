# Report Output Policy

Generated reports must not be written into the active docs root. Keep `docs/`
for curated, durable documentation and short summaries that are useful during
normal development.

## Default Output Paths

Use these ignored locations for raw/generated outputs:

| Report type | Output path |
| --- | --- |
| Onboarding rebuilds and quality runs | `reports/onboarding/` |
| TMDb diagnostics and probes | `reports/tmdb/` |
| UI visual notes that are not screenshots | `reports/ui/` |
| Storage and SQLite diagnostics | `reports/storage/` or `data/diagnostics/` |
| Network logs and probes | `reports/network/` |
| General quality audits | `reports/quality/` |

Screenshots and visual smoke images go under:

```text
tmp/ui/<task-name>/
```

Generated export data goes under:

```text
data/exports/
```

## What Can Be Committed

Commit only curated summaries under:

```text
docs/reports/<topic>/
```

A committed summary should be short and should include:

- date;
- command or scenario;
- key outcome;
- known limitations;
- link or path to regenerated raw output if relevant.

Do not commit full raw dumps, large JSON payloads, local screenshots, cache
snapshots, logs, or one-off audit transcripts.

## Script Defaults

New report scripts should default to ignored output paths under `reports/`,
`data/diagnostics/`, `data/exports/` or `tmp/ui/`.

If a script supports `--output`, examples in docs should use ignored paths.
Only explicitly curated reports should target `docs/reports/`.
