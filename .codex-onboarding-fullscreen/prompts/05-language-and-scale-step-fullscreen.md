# 05 Language And Scale Step Fullscreen

Goal: language and UI scale inside fullscreen onboarding.

Tasks:
1. Language: English / Русский, apply immediately.
2. Scale: live title/card preview, presets 90/100/115/130, save to settings.
3. Full-window layout.
4. No QT_SCALE_FACTOR.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
