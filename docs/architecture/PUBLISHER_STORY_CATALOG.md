# Optional publisher-installed story catalog

The source release does not contain a catalog. Only a separately approved paid
distribution may place a provisioned JSONL at `assets/story-catalog.jsonl`, next
to the launcher or frozen executable (not inside PyInstaller's extraction
directory). No download, key or profile import is involved in selection or
loading. Plot queries are local. Missing sidecar leaves the local profile catalog
as the default. A malformed selected file is an error, not a silent fallback.

Selection order: `preview.py --catalog FILE`, then
`WATCHBANE_STORY_SEED_CATALOG`, then the publisher sidecar, then the profile.
The in-app file picker can replace the selected file for the current session.
For a source-layout staging tree, run `python preview.py --check` without an
override to preflight the sidecar offline through the normal JSONL validator.

Delivery does not authorize redistribution. Approve the exact dataset and
necessary attribution separately before staging it. Do not use private
checkpoints, examples, fictional rows or an unapproved TMDb export. The current
snapshot format uses real typed TMDb identifiers and attributes text to TMDb;
do not use it to disguise another metadata source or fabricate identifiers.
A different source needs an explicit identity/attribution decision first.
Omit `poster_path` from the paid sidecar for an offline package; that optional
field can cause the existing UI to fetch TMDb images during browsing. Preflight
does not fetch posters.
