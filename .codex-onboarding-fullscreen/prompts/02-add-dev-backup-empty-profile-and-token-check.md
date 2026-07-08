# 02 Add Dev Backup Empty Profile And Token Check

Goal: prepare safe dev sandbox.

Tasks:
1. Add dev-only empty runtime profile/database support.
2. Add dev-only candidate pool/onboarding reset support.
3. Always backup before destructive reset.
4. Add TMDb token check helper that never prints token.
5. Add `docs/onboarding_dev_sandbox.md`.

Flags:
- `WATCHBANE_DEV_EMPTY_PROFILE=1`
- `WATCHBANE_DEV_CLEAR_CANDIDATES_ON_START=1`

Tests must use temp DB.

Checks:
- run `py -m compileall desktop app candidates storage tests scripts`
- run targeted tests for touched modules
- run `py -m pytest` on broad/final prompts
- generate screenshots under `screens/tmp_ui/onboarding/` if feasible
- final report must use the format from RULES.md
