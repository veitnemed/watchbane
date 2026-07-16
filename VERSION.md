# Watchbane release identity

| Component | Version | Name | Status |
|---|---|---|---|
| Desktop application | `0.1.1-alpha.1` | **Open Route** | Alpha release |
| Recommendation engine | `ReDeck v0.1.0` | **ReDeck** | Versioned recommendation contract |
| Windows package | `Watchbane-0.1.1-alpha.1-windows-x64.zip` | Folder-based onedir bundle | Windows 10/11, x64 |

Release tag: `v0.1.1-alpha.1`.

## Version policy

- `common/release.py` is the single source of truth for runtime and UI version strings.
- `tools/windows_version_info.txt` carries matching Windows executable metadata.
- Active documentation without its own historical version marker describes this release.
- `ReDeck v0.1.0` identifies the recommendation flow used by this application release: local candidate pool, persisted intent/vector, deck ranking, diversity, impressions, reserve and user actions.
- Alpha means the storage and recommendation behavior is usable and regression-tested, but public APIs and UI details may still change before `1.0.0`.

## Distribution format

The Windows build is **not** a standalone single file. The complete `Watchbane/` directory is the application. Keep `Watchbane.exe` next to `_internal/` and the bundled assets. The published ZIP contains this directory as one unit.

Release archive SHA-256:

```text
D891BB7E8D3B4B69FE3FFB1421D50F8CBA8DD7CC6A2DBBF9F81411F66F59E65E
```
