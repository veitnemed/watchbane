# 13 Animation Polish And Performance

Goal: smooth but not overbuilt animations.

Tasks:
1. Review transition duration/easing.
2. Avoid animation stacking.
3. Disable/reduce animation in tests.
4. Ensure no blocking API/storage calls on UI thread.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
