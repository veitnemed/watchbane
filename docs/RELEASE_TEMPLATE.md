# Release Template

Use this template for GitHub Releases.

## Title

```text
vX.Y.Z - Short Release Name
```

## Description

````markdown
## Highlights

-

## Notes

- Windows + Python 3.13+ is the primary supported setup.
- TMDb flows require a local `TMDB_TOKEN`.
- Runtime data stays local under `data/` and is not committed.

## Quick Start

```powershell
py -m pip install -r requirements.txt
py start_app.py
```
````

## Attachments

Attach release files from:

```text
data/exports/github_release/<version>/
```

Recommended files:

- `watchbane-<version>-source.zip`
- `watchbane-<version>-docs.zip`
- `quick-start-<version>.txt`
- `checksums-sha256.txt`
