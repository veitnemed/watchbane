# Master prompt for Codex

I copied `.codex-onboarding-fullscreen` into the repository root.

Task:
Complete fullscreen onboarding, dev sandbox, token-safe candidate autofill, and visual polish.

Instructions:
1. Read `.codex-onboarding-fullscreen/RULES.md`.
2. Process `.codex-onboarding-fullscreen/prompts/*.md` in filename order.
3. After each prompt:
   - run targeted checks;
   - run `py -m compileall desktop app candidates storage tests scripts`;
   - run `py -m pytest` when broad/final;
   - generate screenshots if possible;
   - write report to `.codex-onboarding-fullscreen/logs/<prompt>.result.md`;
   - commit the step if checks pass.
4. Stop on failing tests, unsafe data deletion risk, token leak risk, or unclear UI architecture.
5. Do not push.
6. Do not create PRs.
