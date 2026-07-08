# 03 Fullscreen Onboarding Routing

Goal: replace small modal/dialog onboarding with full-window onboarding.

Tasks:
1. If onboarding_completed=false, show onboarding as main window central content/full overlay.
2. Do not show empty app behind tiny dialog.
3. Add Skip/Exit safe behavior.
4. Preserve normal startup after completion.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
