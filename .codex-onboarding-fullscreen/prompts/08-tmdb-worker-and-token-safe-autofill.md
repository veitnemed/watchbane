# 08 Tmdb Worker And Token Safe Autofill

Goal: build candidate pool from TMDb without blocking UI.

Tasks:
1. Implement worker/service for onboarding candidate autofill.
2. Read token from existing config/env only.
3. Never print token.
4. Mock TMDb in tests.
5. Store request audit if storage supports it.
6. UI progress states.

Real API calls only manual/dev, not tests.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
