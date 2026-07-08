# 16 Visual Hardening Cycle 01

Find 5 weak spots in fullscreen onboarding visuals. Fix highest-impact one only. Generate before/after screenshots if feasible.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
