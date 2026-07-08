# Codex Movie Add-Title Cycle

Date: 2026-07-08

Scope:
- Extend add-title from TV-only to `media_type=tv|movie`.
- Preserve the service save path: `dataset.storage_movie.add_movie(...) -> dataset.dataset_records.add_dataset_record(...)`.
- Keep UI free of direct watched JSON writes.

Feature steps:
- `000-baseline.md`
- `001-media-type-contract.md`
- `002-003-record-media-type-identity.md`
- `004-005-tmdb-movie-api-normalizer.md`
- `006-008-resolve-save-movie-path.md`
- `009-012-desktop-movie-ui-flow.md`
- `013-015-console-transfer-docs-regression.md`

Hardening steps:
- `101-hardening-domain-boundaries.md`
- `102-hardening-worker-typeerror-fallback.md`
- `103-hardening-update-media-type-preservation.md`
- `104-hardening-gui-polish-screenshot.md`
- `105-hardening-service-facade-coverage.md`
- `106-hardening-storage-schema-safety.md`
- `107-hardening-candidate-transfer-consistency.md`
- `108-hardening-tmdb-client-cache.md`
- `109-hardening-read-model-display.md`
- `110-hardening-docs-and-developer-experience.md`

Final verification:

```powershell
py -m compileall app apis candidates common config dataset desktop posters scripts storage ui web tests
$env:PYTHONDONTWRITEBYTECODE='1'; py -m pytest
```

Visual verification:
- Native Windows screenshot smoke for add-title search dialog.
- Screenshot path: `screens/tmp_ui/movie_add_title_search/search_dialog_movie.png`.
- Platform plugin: `windows`.
- Font probe: `Segoe UI=True`.
