# 15 Final Regression And Cleanup

Goal: finalize fullscreen onboarding.

Tasks:
1. Remove temp hacks that should not ship.
2. Keep useful dev scripts documented.
3. Screenshots: onboarding start 75/100/150, taste 75/100/150, loading 100, final 100.
4. Full tests.

Acceptance: fullscreen onboarding, safe reset/dev scripts, token not leaked, repeatable dev onboarding, candidate autofill can run with user token.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
