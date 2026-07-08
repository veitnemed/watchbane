# 14 Dev Clear Pool On Start Toggle

Goal: temporary dev-only startup cleanup for repeated testing.

Tasks:
1. Implement `WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START=1`.
2. If flag set, backup or use dev DB, clear candidate pool and onboarding generated candidates.
3. Do not clear watched library unless explicit separate flag.
4. Tests with temp DB.
5. Document how to disable/remove before release.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
