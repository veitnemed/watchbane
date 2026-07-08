# 12 Visual Parity Pass Fullscreen

Goal: fix most visible screenshot problems.

Tasks:
1. Generate screenshots for welcome, scale, taste, plan preview, loading, final.
2. Identify top 5 visual issues.
3. Fix top 2 issues.

Acceptance: no tiny dialog, full-window composition, no cramped cards, clear navigation.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
