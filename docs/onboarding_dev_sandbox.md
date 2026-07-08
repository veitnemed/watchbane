# Onboarding Dev Sandbox

Date: 2026-07-08

## Goal

Repeat first-run onboarding safely during development without silently deleting real user data.

## Explicit Flags

- `WATCHBANE_DEV_EMPTY_PROFILE=1`
- `WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START=1`

Both flags are off by default.

## Startup Behavior

`desktop.shell.bootstrap.main()` calls `storage.runtime.apply_dev_startup_reset_from_env()` before runtime initialization.

If either flag is enabled:

1. The active data root is backed up under `data/.../backups/dev_startup/`.
2. `WATCHBANE_DEV_EMPTY_PROFILE=1` removes active SQLite DB files and legacy runtime JSON files.
3. `WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START=1` clears candidate/onboarding SQLite tables without clearing watched records.
4. Runtime initialization recreates the SQLite schema and required directories.

## Local Launcher

For manual visual work:

```powershell
.\.codex-onboarding-fullscreen\local_scripts\launch-main-empty-runtime.ps1 -Repo .
```

Useful smoke mode:

```powershell
.\.codex-onboarding-fullscreen\local_scripts\launch-main-empty-runtime.ps1 -Repo . -AutoCloseSeconds 8
```

The launcher creates a backup in `%TEMP%\watchbane-onboarding-backups\...`, empties the active profile runtime, sets the dev flags, and starts `py start_app.py`.

## Console GUI Mode

For repeated first-run checks without clearing watched records:

```powershell
py start_console.py
# choose: 7 >> Dev GUI: empty candidate pool on startup
```

This starts `start_app.py` with `WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START=1` only. GUI bootstrap backs up the active data root, clears candidate/onboarding tables, then opens the onboarding flow from a zero candidate pool.

## Token Policy

TMDb credentials are discovered from:

- `TMDB_ACCESS_TOKEN`
- `TMDB_TOKEN`
- `TMDB_API_KEY`

Tokens are never printed. `TMDB_API_KEY` is sent as query `api_key`; access tokens are sent as Bearer auth.

## Release Note

The dev flags and `.codex-onboarding-fullscreen/local_scripts` helpers are development-only. They must not be enabled in user startup environments.
