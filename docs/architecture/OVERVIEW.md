# Watchbane architecture

Версия архитектурного среза: **Watchbane 0.1.0-alpha.1 — First Deck** / **ReDeck v0.1 Alpha**. Канонический release contract: [../../VERSION.md](../../VERSION.md).

Watchbane is a local-first PyQt6 application. The desktop UI delegates product operations to application use cases; domain services contain the recommendation and library flows; infrastructure modules own persistence and external API access.

```text
desktop/             PyQt6 views, presenters, workers
app/use_cases/       UI-facing product operations
candidates/          candidate pool, search, onboarding, TMDb acquisition
dataset/             watched library and derived read models
posters/             poster resolution, cache, and downloads
storage/             SQLite runtime and repositories
apis/                remote service clients
config/, common/     configuration and shared utilities
tools/, diagnostics/    maintenance and diagnostics
```

## Candidate flow

`desktop/candidates` calls `app/use_cases/candidate_search.py`. The use case coordinates `candidates/pool_service.py` and `candidates/search_service.py`; writes are exposed through focused use cases such as `candidate_actions.py` and `onboarding.py`.

`candidates/service.py` remains a compatibility facade for the existing console and integrations. New code should import a focused service or an `app/use_cases` module instead of adding logic to that facade.

## Dependency direction

Desktop modules must not import SQLite repositories, TMDb builders, or API compatibility modules directly. `tests/architecture/test_ui_import_boundaries.py` protects this rule.
