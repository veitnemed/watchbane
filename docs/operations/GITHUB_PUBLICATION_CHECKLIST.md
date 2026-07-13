# GitHub Publication Checklist

Things that cannot be fully configured from files in the repository.

## Repository Settings

- Add description: `Local-first PyQt app for watched titles and candidate recommendations`.
- Add website if there is a demo/video later.
- Add topics:
  - `python`
  - `pyqt6`
  - `tmdb`
  - `watchlist`
  - `recommendation-system`
  - `local-first`
  - `desktop-app`
  - `movie-database`
  - `series-tracker`
- Enable Issues.
- Enable Discussions if you want public feedback.
- Protect `main` after the first public release.

## Visuals

- Add 2-4 screenshots to `docs/assets/screens/`.
- Use one screenshot as GitHub social preview.
- Watchbane screenshots:
  - watched list + detail card;
  - candidate filters;
  - candidate detail card;
  - settings tab.

## First Public Release

- Release identity: `Watchbane 0.1.0-alpha.1 — First Deck`.
- Recommendation engine: `ReDeck v0.1 Alpha`.
- Tag `v0.1.0-alpha.1`.
- Attach `Watchbane-0.1.0-alpha.1-windows-x64.zip` and its SHA-256 checksum.
- Write release notes with:
  - what works now;
  - what is local-only;
  - what requires TMDb token;
  - known limitations.

## README Cleanup Before Public Push

- Confirm README badges point to `veitnemed/watchbane`.
- Add screenshots when available.
- Confirm the license choice is intentional.
