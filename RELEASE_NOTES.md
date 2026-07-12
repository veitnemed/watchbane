# Release notes

## Release readiness

- Windows desktop build: PyInstaller onedir (`dist/Watchbane/Watchbane.exe`). Keep `_internal/` beside the executable.
- Runtime installation: `py -m pip install -r requirements.txt`.
- Developer/test installation: `py -m pip install -r requirements-dev.txt`.
- Optional Plotly, WebEngine, and ML tooling: `py -m pip install -r requirements-experiments.txt`.

## Compatibility

The application remains local-first. Existing SQLite data, settings, candidate pools, and poster cache use the established runtime paths; this release introduces no SQLite schema migration.

The candidate, TMDb, watched-library, and poster refactors retain compatibility facades for legacy console and UI call paths.

## Known operational limits

- TMDb startup requires a user-provided token and reachable TMDb network endpoint.
- Plotly/WebEngine analytics are optional; the UI displays a fallback if these components are absent.
- Release artifacts have been smoke-tested on Windows only. Publish the onedir folder as a unit.

## Publication checklist

1. Confirm CI is green for the release commit.
2. Build with `scripts/build_desktop.ps1`.
3. Smoke-launch `dist/Watchbane/Watchbane.exe` with an isolated `WATCHBANE_DATA_DIR`.
4. Attach the complete `dist/Watchbane/` directory and a checksum to the release.
5. Publish the Git tag and release only after approving the artifact.
