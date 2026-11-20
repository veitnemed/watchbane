# Story catalog acquisition preview — 2026-11-19

This increment adds an explicit home-screen action, **«Заполнить каталог из TMDb»**, after the verified profile-vector-cache slice. No automatic onboarding/token prompt occurs on startup; original fictional demo and local search work without network credentials. Previous ZIP and patches are preserved, and GitHub is unchanged.

## Flow and reused components

The home screen shows available searchable description count. Clicking import opens the existing masked `TmdbCredentialsPanel` only if no credentials exist. Its existing `TmdbStartupValidateWorker` handles validation/storage. Successful authorization continues import; closing the credential dialog returns to offline search. No token is embedded or shipped.

Import reuses `FilterReplenishWorker` (progress, failure and cancellation), the existing `_build_filter_replenish_tmdb_client` official discover/details adapter, existing TMDb normalizers/safety filter and `import_tmdb_candidates_to_common_pool` transaction. The new narrow service uses fixed discovery parameters: first popularity-sorted page of movies and TV, up to 15 IDs from each, `include_adult=False`, Russian locale first. It does not read the user's taste profile or send library contents/search strings to TMDb. Credentials are sent through the existing API authorization path only after the explicit action.

Each new ID gets details in ru-RU; absent top-level overview triggers en-US details. Empty descriptions after fallback are omitted. English localized text is labelled **«английский fallback»** in story cards. At most 30 titles, 2 discover + 30 RU details + 30 EN fallback calls per operation (excluding existing authorization/provider-internal behavior). This is a bounded sample, not a complete index; exact count depends on duplicates, missing metadata and safety checks. Changing TMDb popularity pages can add new titles on a later run, but repeating an unchanged response does not duplicate entries. Existing IDs are not overwritten or automatically retranslated in this slice.

All fetched candidates stay in memory until both media types finish. Cancellation/error before the final transaction leaves the common pool unchanged. Existing HTTP/details caches may update during network calls. Cancellation waits for the current provider call to return; no promise of instantaneous network interruption. Once the final atomic import has committed, a late cancel cannot undo it; UI reports the completed import. Existing watched/saved/hidden identities remain authoritative. A storage exception is displayed as a recoverable error; importer transaction handles rollback.

After success the available count updates, mode becomes automatic, and a nonempty current query reruns against the new catalog without restart. In-flight story search queues the latest query, and changed documents invalidate the RAM index naturally. New passage vectors use the profile-only disk cache from the prior slice. No retrieval or ranking changes in this increment.

## Tests and provenance

`tests/test_story_catalog.py` uses original synthetic fixtures; no copyrighted dataset. Tests cover existing official adapter methods, RU→EN fallback labels, request parameters without query strings, both media types, bounded work, missing overviews, unchanged repeated import, preserved hidden/watched/saved states, errors after partial fetching and cancellation before commit.

`tests/desktop/test_story_catalog_flow.py` runs actual Qt with a blocked network and mocked TMDb responses: clean home → offline demo → existing masked auth panel and validation worker → import worker → visible real local records → automatic rerun → repeated import. A separate flow checks cancel/error/retry states without loss. This is **mock TMDb**, not a live API integration test. No personal library or real token was used.

```bash
WATCHBANE_TEST_MODEL_DIR=../watchbane-models/multilingual-e5-small-portable QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_story_catalog.py tests/desktop/test_story_catalog_flow.py tests/test_story_search.py tests/test_story_semantic.py tests/test_story_vector_cache.py tests/desktop/test_story_flow.py -q
# 61 passed with real local E5, TMDb mocked.
```

## Three screenshots

Real running `QApplication`/main window, captured with `QWidget.grab()` on Linux **Qt offscreen**, not a visual mockup or Windows screenshot. Two scales, 1 and 1.25. Each has three stages:

1. `01-home.png`: empty isolated profile, visible search and import button, zero local descriptions; no auth dialog.
2. `02-query.png`: entered Russian query before submission.
3. `03-results.png`: actual FP32 E5 retrieval over the original 30 fictional demo stories, explicit demo badges and source excerpts. This does not depict a live TMDb import.

PNG files live outside the source ZIP in `screens/tmp_ui/story-catalog/scale100` and `scale125`. No personal data or foreign synopses appear. Images must be inspected after capture, as done in the handoff report.

```bash
.venv/bin/python -m tools.screenshots.capture_story_catalog_preview --runtime-root /tmp/NEW-story-capture --output-dir /tmp/story-capture --model-dir /path/to/verified-e5 --scale 1
```

## Manual Windows acceptance — not executed

Follow SOURCE_PREVIEW.md with Python 3.13, a fresh copied/disposable profile and portable FP32. Verify clean startup has search/import but no forced auth; demo works offline. Click import, cancel auth and continue demo. Then use your own legitimate TMDb credentials via the masked existing panel, confirm bounded movie/TV import, visible count and automatic query rerun. Try offline/error/cancel/retry, reopen app and saved titles, and repeat import to check duplicates/status preservation. Check EN fallback labels where the provider supplies no RU overview. Keep real credentials/data out of screenshots/reports. Linux mock tests do not establish Windows or live-network behavior.

## Remaining limits

No live TMDb token/API test was performed. Network availability, credential handling on a real Windows machine and endpoint responses still need that manual run. Existing provider timeout/retry/cache behavior is reused; details calls may take longer than the discover adapter's interactive timeout. Catalog is a fixed small popularity sample, not an exhaustive themed discovery feature. No requests contain the plot query. Existing cold E5 model-loading UI pause and memory costs remain; no additional model downloads or new paid services. This product uses the TMDB API but is not endorsed or certified by TMDB.

Final verification: full Linux suite 1752 passed / 25 failed / 8 skipped; failure IDs identical to the prior cache slice (no new failures). All six captured PNG (three stages × scales 1/1.25) were opened and visually checked: search/import controls, count, demo provenance, first card excerpt and action are readable without overlap. The lower-ranked thematic mismatch remains visible rather than presented as an exact plot match. `git diff --check` passed.
