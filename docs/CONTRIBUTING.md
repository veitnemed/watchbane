# Contributing

Thanks for taking a look at Watchbane.

The project is local-first and intentionally keeps UI, domain logic and storage boundaries separate.

## Setup

```powershell
py -m pip install -r requirements.txt
py -m pytest
```

Run the app:

```powershell
py start_app.py
```

Run the console UI:

```powershell
py start_console.py
```

## Architecture Rules

- UI code lives in `desktop/`, `ui/`, `web/`, `app/`.
- Domain logic lives in `dataset/`, `candidates/`, `posters/`.
- Infra lives in `apis/`, `storage/`, `config/`, `common/`.
- UI should call services instead of writing `data/*.json` directly.
- Domain modules must not import `desktop`, `ui` or `web`.
- Scripts should stay thin. Move reusable logic into Domain or Infra.

Read more:

- `LOGICAL_ARCHITECTURE.md`
- `PROJECT_MAP.md`
- `add_functions.md`
- `AGENTS.md`

## Pull Requests

Good PRs are small and focused:

- describe the user-facing change;
- mention changed layers;
- include tests for behavior changes;
- avoid unrelated formatting churn;
- do not commit runtime data from `data/`, caches, reports or local backups.

## Tests

For narrow changes, run focused tests.

For larger changes:

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
py -m pytest
```

No real TMDb/KP/IMDb network calls should be required in unit tests.
