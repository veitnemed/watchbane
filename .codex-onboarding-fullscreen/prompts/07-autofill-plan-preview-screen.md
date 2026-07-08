# 07 Autofill Plan Preview Screen

Goal: show deterministic autofill plan before API calls.

Tasks:
1. Convert answers into quotas: media, release, vibe, origin.
2. Show friendly summary.
3. Buttons: build candidate pool / skip.
4. No API call yet.

Tests: quotas sum to target; ru origin; non-ru skips origin.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
