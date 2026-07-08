# 10 Final Screen And Open Candidates Tab

Goal: final onboarding screen.

Tasks:
1. Show candidates added count and next action.
2. Mark onboarding completed.
3. Open Candidates tab/main candidate view.
4. If zero candidates due to token/API error, allow finish and show retry action.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
