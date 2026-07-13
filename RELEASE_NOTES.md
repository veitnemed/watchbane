# Watchbane 0.1.0-alpha.1 — First Deck

Recommendation engine: **ReDeck v0.1 Alpha**

Release tag: `v0.1.0-alpha.1`

Target: Windows 10/11 x64

## What works

- Local-first watched, saved and hidden collections with user ratings.
- Persisted recommendation direction, filters and recommendation vector.
- ReDeck deck ranking, diversity, impressions, reserve and refill lifecycle.
- Movie and series detail cards, TMDb metadata and poster cache.
- RU/EN interface and independent 75/100/150% application scale.
- SQLite backup, migration and startup recovery.
- User-owned TMDb credential lifecycle; no shared token is bundled.
- Offline access to already stored local data.

## Release hardening

- `1574 passed, 1 skipped` in the final full regression suite before release packaging.
- Native Windows movie/tv visual matrix checked at 75%, 100% and 150%.
- Existing-profile upgrade from schema v4 to v6 and immediate restart verified.
- Worker shutdown, repeated actions, large pools, corrupt posters and FTS fallback exercised.
- Immediate and delayed packaged-window shutdown verified with `exit 0`.
- Retired QtWebEngine/Plotly runtime dependency removed from the base desktop package.

## Distribution

The release artifact is `Watchbane-0.1.0-alpha.1-windows-x64.zip`. It contains a folder-based PyInstaller onedir build:

```text
Watchbane/
  Watchbane.exe
  _internal/
```

Extract the complete folder and run `Watchbane.exe`. Do not move the EXE away from `_internal/`.

SHA-256: `C837527B554119336D38AC68096E9E468DB5D1CFDFE188E5BA6880AC77E42780`.

## Known alpha limits

- Initial online setup and new TMDb discovery require a user-provided TMDb Read Access Token and a reachable TMDb endpoint.
- The build is smoke-tested on Windows x64 only.
- Alpha releases may change UI details and internal recommendation contracts before 1.0.
- Analytics experiments remain optional and are not part of the base release archive.

## Upgrade and data safety

The application remains local-first. Existing SQLite data, settings, candidate pools, recommendation deck and poster cache use the established runtime paths. The release has been tested against both clean and migrated profiles.
