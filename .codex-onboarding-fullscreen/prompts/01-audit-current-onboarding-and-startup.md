# 01 Audit Current Onboarding And Startup

Goal: find why onboarding appears as a small dialog over an empty app.

Tasks:
1. Locate onboarding/startup code.
2. Locate main window first-run routing.
3. Map widgets/dialogs/services/storage.
4. Create `docs/onboarding_fullscreen_audit.md`.
5. Generate current screenshot if feasible.

Do not redesign yet.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
