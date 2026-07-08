# 11 Screenshot Helper For Onboarding

Goal: reusable onboarding screenshot script.

Tasks:
1. Add `scripts/capture_onboarding.py`.
2. Support --step, --scale, --language, --output, --empty-profile.
3. Native Windows Qt platform when available.
4. Print platform/font probe.
5. Save under `screens/tmp_ui/onboarding/`.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
