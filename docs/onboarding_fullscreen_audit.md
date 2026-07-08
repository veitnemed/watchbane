# Fullscreen Onboarding Audit

Date: 2026-07-08

## Startup Path

- Entry point: `start_app.py` -> `desktop.shell.bootstrap.main()`.
- Runtime layout is initialized before `QApplication` through `storage.runtime.ensure_runtime_data_layout()`.
- Main window: `desktop.shell.main_window.WatchedMoviesWindow`.
- Main tabs are built by `desktop.shell.tabs.build_main_tabs()` and registered in a `QTabWidget`.
- First-run onboarding gate: `candidates.service.should_show_onboarding_autofill()`.

## Previous Issue

The onboarding UI was implemented as `OnboardingAutofillDialog.open()` from `WatchedMoviesWindow.maybe_show_onboarding_autofill()`. That made it appear as a separate modal dialog over an otherwise empty application shell.

## Current Routing

The main window now uses a root `QStackedWidget`:

- page 0: normal `mainTabs`;
- page 1: onboarding view when first-run autofill is needed.

This keeps onboarding as full-window central content. The normal tabs are not shown behind a tiny modal. When onboarding finishes or is skipped, the root stack returns to `mainTabs` and focuses Candidates.

## Widget And Service Boundary

- UI class: `desktop.onboarding.wizard.OnboardingAutofillDialog`.
- Worker class: `desktop.onboarding.worker.OnboardingAutofillWorker`.
- Service facade: `candidates.service.build_onboarding_candidate_pool()`.
- Deterministic plan facade: `candidates.service.get_onboarding_autofill_plan_view()`.
- Storage/audit repository: `storage.sqlite.onboarding_repository`.

The UI does not call TMDb directly. API work runs in `OnboardingAutofillWorker`.

## Screenshot Tooling

- Existing helper: `scripts/capture_onboarding_wizard.py`.
- Full prompt-pack helper: `scripts/capture_onboarding.py`.
- Screenshots are generated under `screens/tmp_ui/onboarding/`.
- On Windows, screenshot helpers prefer `QT_QPA_PLATFORM=windows` and print platform/font probes.

## Known Risks

- The onboarding view still subclasses `QDialog` for compatibility with existing tests/signals, but it is embedded into the main window stack as a widget during app startup.
- Full animation polish is intentionally small: fade transition only, no heavy motion system.
