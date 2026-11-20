# Windows frozen bundle audit (not compliance clearance)

On the Windows builder, from the same Python environment used to build:

```powershell
python -m tools.qa.audit_windows_distribution --profile semantic --bundle dist/Watchbane
```

Use `--profile lexical` for a lexical-only build. Omit `--bundle` to inventory
the current runtime packages even without a Windows build. The report identifies
the **audit host**, not the target OS of an arbitrary directory. A Linux report
cannot substitute for the exact Windows wheels and bundle.

The audit prints JSON. Use `--summary` in CI to print versions, counts and
review flags without individual paths or hashes. By default, the report includes package versions and installed license/notice file
digests from distribution metadata, plus curated bundle file digests. It skips
links/reparse points, known local data/profile folders and unrecognized
extensions, imposes file/byte caps, and does not extract archives or inspect
models, databases, plot JSONL or user profiles. Use only a clean staged bundle,
not a directory containing personal data. Give tested exact companion notices
dedicated `licenses/<package>/` paths. Required package license files and, in the
semantic profile, ONNX Runtime third-party notices are mechanically checked.
PyInstaller is listed as a build input; it is not a required bundle notice.
Missing notices or incomplete local package metadata result in a nonzero exit
with review flags. Presence does not establish accuracy or completeness.

Keep dependency pins/hashes and version-matched license/source access records
with the publication review. Audit the compiled libraries, assets, source
availability, redistribution lane, and replacement/relink instructions
separately. This tool is not an SBOM generator, does not verify source
correspondence and must not be used to declare license compliance.
