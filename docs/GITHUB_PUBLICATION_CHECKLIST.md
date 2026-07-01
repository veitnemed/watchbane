# GitHub Publication Checklist

Things that cannot be fully configured from files in the repository.

## Repository Settings

- Add description: `Local-first PyQt app for watched titles and candidate recommendations`.
- Add website if there is a demo/video later.
- Add topics:
  - `python`
  - `pyqt6`
  - `tmdb`
  - `imdb`
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

- Add 2-4 screenshots to `screens/`.
- Use one screenshot as GitHub social preview.
- Watchbane screenshots:
  - watched list + detail card;
  - candidate filters;
  - candidate detail card;
  - analytics/information tab.

## First Public Release

- Tag `v0.1.0`.
- Use [RELEASE_TEMPLATE.md](RELEASE_TEMPLATE.md) for the release body.
- Write release notes with:
  - what works now;
  - what is local-only;
  - what requires TMDb token;
  - known limitations.

## README Cleanup Before Public Push

- Confirm README badges point to `veitnemed/watchbane`.
- Add screenshots when available.
- Confirm the license choice is intentional.
