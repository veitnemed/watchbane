# 04 Onboarding Visual Shell And Motion

Goal: create polished fullscreen onboarding shell.

Tasks:
1. Cinematic Watchbane background.
2. Large centered onboarding card/panel.
3. Progress dots/bar.
4. Back / Next / Skip footer.
5. Smooth step transition with QPropertyAnimation or equivalent.
6. Animation disable/reduce in tests.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
