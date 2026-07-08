# Fullscreen onboarding rules

Context:
Watchbane is a local-first Python/PyQt6 desktop app with SQLite runtime storage, TMDb candidate discovery, and candidate pool.

Goal:
First-run onboarding must become a full-window guided experience, not a small dialog over an empty app.

Hard rules:
- Do not push.
- Do not create PRs.
- Do not commit screenshots.
- Do not hardcode or print TMDb tokens.
- Do not commit `.env`, token files, real SQLite DBs, screenshots, or backup archives.
- Do not silently delete real user data.
- Every destructive/dev reset action must require explicit flag or dev script.
- UI must not call TMDb or storage directly from widgets. Use service/worker layer.
- API calls must run in worker/thread, never block the UI thread.
- In tests, use mocked TMDb client.
- If a screenshot was generated but not visually inspected, say so honestly.
- Keep Russian text UTF-8, no mojibake.

TMDb token policy:
- Use existing project token discovery if present.
- Otherwise read from environment:
  - `TMDB_API_KEY`
  - `TMDB_ACCESS_TOKEN`
- Never store token in SQLite.
- Never write token into logs.
- Never print token in reports.

Dev sandbox policy:
- Add scripts/flags for empty runtime data.
- Prefer temp/dev DB path over deleting real `data/`.
- If clearing real candidate pool is requested, create backup first.
- Add explicit dev-only flags:
  - `WATCHBANE_DEV_EMPTY_PROFILE=1`
  - `WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START=1`
- These flags must be off by default.

Visual target:
- full-window onboarding inside the main window;
- smooth QStackedWidget-like transitions;
- large selectable cards;
- progress dots/bar;
- visible Back / Next / Skip;
- cinematic Watchbane blue style;
- final screen opens Candidates tab or main app with starter pool.

Verification:
- Small UI tweak: compileall + targeted tests + one screenshot at 100%.
- Layout/animation flow: compileall + targeted tests + screenshots at 0.75 / 1.0 / 1.5.
- Final: compileall . + full pytest + onboarding screenshots for start/taste/loading/final.

Final report:
## Prompt
...
## Summary
...
## Screenshots / visual checks
...
## Changed files
...
## Checks run
...
## Behavior change
...
## Risks / follow-up
...
