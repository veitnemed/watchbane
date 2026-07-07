# Watchbane

[![Tests](https://github.com/veitnemed/watchbane/actions/workflows/tests.yml/badge.svg)](https://github.com/veitnemed/watchbane/actions/workflows/tests.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/desktop-PyQt6-41cd52.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Local first](https://img.shields.io/badge/data-local--first-111827.svg)](docs/DATA_STORAGE_PLAN.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Local-first movie & series recommendation lab.**

Watchbane is a PyQt desktop app for building a personal recommendation system around your own taste: watched titles, candidate pools, transparent scoring, TMDb metadata, and a clean core for future ML/LLM experiments.

It is not another locked watchlist. Watchbane is a local-first workspace where your data stays inspectable, recommendation signals stay visible, and the application architecture remains testable as the project grows.

<p align="center">
  <img src="screens/main.png" alt="Watchbane desktop watched library with poster, ratings and title details" width="100%">
</p>

<p align="center">
  <strong>Your watched library, candidate pool, ratings, metadata and recommendation experiments in one local desktop workspace.</strong>
</p>

## Why Watchbane Exists

Streaming platforms optimize for engagement.

Watchbane is designed for a different question:

> What should I actually watch next, based on my own history, filters, taste and scoring rules?

The project combines a local watched library, external metadata, candidate discovery and transparent recommendation logic. The goal is to make recommendations understandable, reproducible and easy to experiment with.

```text
your watched dataset
  + external metadata
  + candidate discovery
  + transparent scoring
  + filters
  + future ML/LLM experiments
  = better watch decisions
```

## Core Principles

- **Local-first**: your watched library, candidate pool, ratings and metadata are stored locally. The app can enrich data with external sources, but your personal dataset remains yours.
- **Transparent scoring**: recommendations should not be a black box. Watchbane exposes signals such as TMDb rating, votes, popularity, country, genres, metadata completeness and personal scoring.
- **Candidate discovery**: the app is not only a watched-list manager. It keeps a persistent candidate pool that can be searched, filtered, cleaned, hidden, transferred and revisited.
- **ML-ready architecture**: the desktop UI is one client over a testable recommendation core, so scoring, filters, dataset flows and candidate sources can evolve into ML/LLM experiments.

## What Makes It Different

| Instead of... | Watchbane gives you... |
| --- | --- |
| A throwaway search result | A persistent candidate pool you can filter, clean and revisit |
| A locked platform watchlist | Local JSON data you can inspect and back up |
| Blind recommendations | Visible signals: TMDb rating, votes, popularity, country, type, metadata completeness |
| Manual copy-paste | Add-title and candidate-transfer flows with preview and confirmation |
| A pile of scripts | Clear UI / Domain / Infra / Project architecture |
| UI-only logic | A testable domain core ready for recommendation experiments |

## Current Experience

- **My library**: browse watched titles with posters, your ratings, TMDb signals, metadata and detail cards.
- **Candidates**: search a shared pool of possible next titles, hide noise, transfer good picks.
- **Settings**: choose UI scale plus independent interface/data languages for desktop display and future metadata requests.
- **TMDb-only build flow**: discover candidates by country/mode, fetch TMDb Details, score them, import into the shared pool.
- **Poster cache**: keep preview posters local and avoid waiting on CDN during normal browsing.
- **Console tools**: maintenance, diagnostics, imports and longer-running operations stay available.

## Recommendation Lab, Not Just a Watchlist

Watchbane is useful as a normal personal media app, but its main direction is broader:

```text
watchlist app
  -> candidate discovery tool
  -> transparent recommendation engine
  -> ML/LLM experimentation lab
```

The project is designed to support experiments such as heuristic recommendation scoring, trainable weights from personal ratings, feature extraction from metadata, embeddings for similarity search, LLM-generated explanations, sandbox datasets, alternative candidate sources and local evaluation of recommendation quality.

## Preview

<table>
  <tr>
    <td width="50%">
      <img src="screens/main.png" alt="Watched library screen">
    </td>
    <td width="50%">
      <img src="screens/candidates.png" alt="Candidate pool screen">
    </td>
  </tr>
  <tr>
    <td><strong>My library</strong><br>Personal ratings, TMDb signals, posters, metadata and synopsis.</td>
    <td><strong>Candidate pool</strong><br>Ranked recommendations with filters, hide/transfer actions and vote signals.</td>
  </tr>
</table>

## Built For

- people who rate films and series seriously;
- local-first workflows;
- custom recommendation experiments;
- personal media datasets;
- ML/LLM-assisted recommendation research;
- Python/PyQt projects that should stay understandable while growing.

## Architecture

Watchbane keeps the physical folder layout simple, but treats the project as four logical zones:

| Zone | Purpose |
| --- | --- |
| `UI` | `app/`, `desktop/`, `ui/`, `web/` |
| `Domain` | `dataset/`, `candidates/`, `posters/` |
| `Infra` | `apis/`, `storage/`, `config/`, `common/` |
| `Project` | `tests/`, `docs/`, `scripts/`, `assets/` |

Start here if you want to understand the code:

- [Logical architecture](docs/LOGICAL_ARCHITECTURE.md)
- [Project map](docs/PROJECT_MAP.md)
- [Desktop module map](docs/DESKTOP_MODULE_MAP.md)
- [Detailed docs README](docs/README.md)

Architecture goals:

- keep PyQt widgets focused on layout, rendering and user interaction;
- keep dataset, candidate and scoring logic testable without Qt;
- route writes through domain services instead of UI code;
- keep candidate sources replaceable;
- keep recommendation signals inspectable;
- keep UI scaling and language behavior covered by guardrail tests.

## Run It

Watchbane is developed primarily on Windows with Python 3.13+.

```powershell
py -m pip install -r requirements.txt
py start_app.py
```

Console UI:

```powershell
py start_console.py
```

Tests:

```powershell
py -m pytest
```

Desktop interface scale:

- open `Настройки` and choose the interface scale under `Интерфейс`;
- default scale is `100%`;
- available scale range is `50%` to `200%`;
- this is separate from Windows display scaling / OS DPI;
- scale changes require restarting the desktop app;
- local component tuning is documented in [UI scaling](docs/ui-scaling.md);
- `QT_SCALE_FACTOR` is a Qt testing/debug override and is not recommended for normal Watchbane use.

Desktop language settings:

- open `Настройки -> Интерфейс -> Язык`;
- `interface_language` changes desktop labels, buttons and messages;
- `data_language` changes displayed titles/descriptions/genres/countries when localized data exists and is used for desktop-initiated TMDb requests;
- supported values are Russian and English;
- language changes apply after restart or screen reload depending on the setting.

Existing local JSON created before bilingual data support can be backfilled from TMDb locale responses:

```powershell
py scripts/backfill_watched_localized_from_tmdb.py --target all --language en
```

The backfill adds `localized.en.title/overview`, creates backups next to the JSON files and keeps dataset keys and legacy fields unchanged.

Public setup for candidate discovery requires only `TMDB_TOKEN` in the environment, `.env.local`, or `tmdb.env`.

No KP API token or local IMDb dataset is required for the public product.

## TMDb-Only Candidate Pool

The public recommendation flow is TMDb-only:

1. TMDb Discover finds possible TV titles by country, year and genre slices.
2. TMDb Details adds metadata: overview, poster, genres, countries, external ids, credits, keywords and providers.
3. Watchbane normalizes each item into a local candidate contract.
4. Local scoring computes `quality_score`, `hidden_gem_score` and `final_score`.
5. The result can be imported into `data/candidates/pool.json` and searched from GUI/console.

The candidate contract does not require KP/IMDb ratings. `imdb_id` may exist only as an external id.

See [TMDb-only candidate flow](docs/TMDB_ONLY_CANDIDATE_FLOW.md) for the full contract, migration scripts, refresh scripts, scoring notes and limitations.

## TMDb-Only Add Title

Adding a watched title is also TMDb-only:

1. enter an input title;
2. search TMDb TV;
3. fetch TMDb Details;
4. preview title/year/metadata/poster/genres;
5. enter your `user_score`;
6. save into the watched dataset.

KP API is not needed. A local IMDb dataset is not needed. IMDb rating/votes are not used. `imdb_id` may be stored only as an external id returned by TMDb.

## Analytics Helpers

Analytics/chart helpers are internal and are not registered as a main desktop tab:

- watched genre counts;
- candidate pool genre counts;
- a chart constructor for local dependencies.

The constructor supports watched titles and candidate pool data, bar/function chart types, X axes such as year, genre, country, TMDb rating/votes/popularity, and Y metrics such as title count, average user score, average TMDb rating and average final score. No network calls are made while building these charts.

Useful maintenance commands:

```powershell
py scripts/migrate_candidate_pool_tmdb_only.py --dry-run
py scripts/refresh_candidate_pool_from_tmdb.py --dry-run
py scripts/migrate_watched_raw_scores_tmdb_only.py --dry-run
py scripts/refresh_watched_from_tmdb.py --dry-run
```

## ML / LLM Experimentation Direction

Watchbane is not an ML product yet. It is a foundation for recommendation experiments built on clean local data, explicit candidate sources, transparent scoring and regression tests.

Possible future layers include learned scoring weights from personal ratings, recommendation quality metrics, embedding-based similarity, local title clustering, LLM-generated recommendation explanations, hybrid scoring with explicit user controls and daily trend imports as candidate sources.

## Repository Notes

- Runtime user data lives under `data/` and is ignored by git.
- Temporary UI screenshots live under `screens/tmp_ui/` and are ignored by git.
- Legacy experiments live under `archive/` and are not active runtime.
- Contribution and project hygiene docs live in [`docs/`](docs/).
- Local cleanup rules are documented in [workspace housekeeping](docs/WORKSPACE_HOUSEKEEPING.md).

## Contributing

Issues and focused pull requests are welcome, especially around GUI polish, candidate ranking, metadata quality and offline tests.

- [Contributing](docs/CONTRIBUTING.md)
- [Security](docs/SECURITY.md)
- [Code of conduct](docs/CODE_OF_CONDUCT.md)

## License

MIT. See [LICENSE](LICENSE).
