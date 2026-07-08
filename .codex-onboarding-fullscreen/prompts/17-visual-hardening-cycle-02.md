# 17 Visual Hardening Cycle 02

Focus: animations and transitions. Find 3 weak spots, fix one. Do not change candidate logic.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
