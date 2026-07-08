# 09 Loading Screen And Cancel Flow

Goal: polished loading and cancel flow.

Tasks:
1. Animated loading/progress screen.
2. Current bucket label without technical noise.
3. Cancel/skip.
4. Worker stops safely.
5. No UI freeze.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
