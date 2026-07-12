# 000 Baseline

Date: 2026-07-08

Repo: `D:\VS PROJJJ\vscode projects\watchbane-codex-movie-lab`

Branch: `experiment/movie-save`

Base commit: `43d640e Merge codex hardening cycles`

Result:
- Clean worktree created via `git worktree add`.
- `py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests` passed.
- `PYTHONDONTWRITEBYTECODE=1 py -m pytest` passed: `756 passed, 1 skipped`.

Notes:
- Initial parallel compile/test probe was discarded because simultaneous writes to `__pycache__` caused transient Windows `PermissionError` noise and a Qt access violation during tests.
- Subsequent checks were run sequentially and passed.
