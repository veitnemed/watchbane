# Watchbane 0.1.1-alpha.1 — Open Route

Recommendation engine: **ReDeck v0.1.0**

Release tag: `v0.1.1-alpha.1`

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
- A guarded **Попробовать обход** flow on the token screen for affected TMDb routes.
- Fixed endpoint validation, UAC elevation, timestamped `hosts` backup, marked-block-only updates, DNS flush and automatic rollback on failed post-check.

## Release hardening

- Applying settings now builds a populated deck from fast TMDb Discover candidates whose genres are represented by `genre_ids`.
- Profile registry paths remain anchored to the shared application data root after switching profiles.
- Settings now include a guarded factory reset that removes all local profiles and caches without a backup, preserves only the current TMDb credential and restarts onboarding from language/UI scale.
- Recommendation loading starts only after explicit Apply or Refresh; deck generation and poster loading no longer block the UI.
- Qt workers use bounded cooperative shutdown instead of indefinite waits.
- `1623 passed, 1 skipped` in the final full regression suite before release packaging.
- Native Windows movie/tv visual matrix checked at 75%, 100% and 150%.
- Existing-profile upgrade from schema v4 to v6 and immediate restart verified.
- Worker shutdown, repeated actions, large pools, corrupt posters and FTS fallback exercised.
- Ten isolated packaged cold starts and shutdowns completed with `exit 0`; the window appeared in 754–843 ms (776 ms average) on the release machine.
- The ZIP-extracted build was launched from an isolated runtime and closed normally with `exit 0`.
- Retired QtWebEngine/Plotly runtime dependency removed from the base desktop package.

## Distribution

The release artifact is `Watchbane-0.1.1-alpha.1-windows-x64.zip`. It contains a folder-based PyInstaller onedir build:

```text
Watchbane/
  Watchbane.exe
  _internal/
```

Extract the complete folder and run `Watchbane.exe`. Do not move the EXE away from `_internal/`.

SHA-256: `D891BB7E8D3B4B69FE3FFB1421D50F8CBA8DD7CC6A2DBBF9F81411F66F59E65E`.

## Known alpha limits

- Initial online setup and new TMDb discovery require a user-provided TMDb Read Access Token and a reachable TMDb endpoint.
- The build is smoke-tested on Windows x64 only.
- Alpha releases may change UI details and internal recommendation contracts before 1.0.
- Analytics experiments remain optional and are not part of the base release archive.

## Upgrade and data safety

The application remains local-first. Existing SQLite data, settings, candidate pools, recommendation deck and poster cache use the established runtime paths. The release has been tested against both clean and migrated profiles.

---

# Watchbane story-search-preview.2

Это отдельный исходный pre-release поиска по сюжету, не обновление Windows EXE выше. Начните с [инструкции запуска](SOURCE_PREVIEW.md).

- В поставке нет вымышленных или временных карточек. В чистом профиле приложение не изображает заполненный каталог: нужны реальные локальные описания или явный импорт TMDb.
- Можно подключить локальный снимок TMDb JSONL без автоматического добавления его в библиотеку и по желанию использовать внешнюю локальную модель E5. Без модели остаётся ограниченный текстовый поиск.
- Архив формируется из закреплённого Git-коммита и поставляется с манифестом файлов и SHA-256. Ни снимок, ни личные данные, ни ключ, ни веса модели не распространяются вместе с исходниками.
- Это экспериментальная версия. Гарантий полноты каталога и точности сопоставления каждого сюжетного условия нет.

## Story Search Preview 3 (source pre-release)

- `Файл каталога…` opens an existing Watchbane JSONL directly from the search window. The file is verified off the UI thread and does not import its rows into the collection or require TMDb credentials. The choice lasts until the app closes; the same menu returns to the profile catalog.
- A failed or cancelled file choice leaves the old results in place. Replacing a file and searching again works even when all old entries were filtered out.
- The selected E5 folder is remembered in the profile. Explicitly switching to word search forgets the saved selection; startup overrides remain available.
- Both search modes recognize a limited set of obvious non-film instructions. The semantic ranker can still return weak hits, especially on multiple plot constraints and cross-language synopses.
- The attached archive contains source code only: no installer, model, live data, or keys. See `SOURCE_PREVIEW.md` to start.

## Story Search Preview 4 (source pre-release)

- Reviewed and saved titles now use stable IDs for action routing. Known different films with the same title and year do not share statuses or overwrite ratings; alternate names of the same known item do not duplicate saved or hidden entries.
- Existing supported aliases are shown once without a bulk database rewrite. A failed state transition leaves the prior state intact. Records already overwritten on earlier versions are not automatically restored.
- Manual adds and reviewed candidate transfers write a single watched row atomically without replacing unrelated rows. Long Unicode titles no longer fail at poster lookup.
- Incompatible backup schemas are rejected before the active database is replaced; supported older backups remain restorable.
- Mentions of films and dates inside a plot no longer accidentally filter the result type or release year. Name-like Cyrillic words within queries are not silently corrected.
- Added reproducible offline BM25 and character TF-IDF comparison tools for development. Product ranking is unchanged.
- The pre-release is source only. No user profiles, catalogs, model weights, keys or Windows executable are included.
