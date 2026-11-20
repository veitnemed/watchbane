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

## Clean Windows and Visual C++ v14

The [observed Windows Server 2025 runner image](https://github.com/actions/runner-images/blob/win25-vs2026/20261103.298/images/windows/Windows2025-VS2026-Readme.md#installed-software)
ships the Visual C++ 2022 x64 runtime 14.51.36247. [ONNX Runtime's Windows requirements](https://onnxruntime.ai/docs/install/#requirements)
name Visual C++ 2019; see [Microsoft's supported v14 versions](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).
Removing Python from PATH does not remove that prerequisite from the runner.

The audit reports fixed MSVC DLL *names found in the bundle* separately from
v14 registrations *observed on the build host*. Neither list proves which DLL
the app loads, clean-host independence, or redistribution rights. Before a
consumer release, verify the exact archive SHA, test its normal install, model
download and first real semantic search on a clean supported desktop Windows
image, and record the runtime before launch. Verify app-local DLL use or the
installer's supported prerequisite handling; do not remove runtime libraries
from an existing machine to simulate this.

For the audit row dated 20 November, the exact Windows wheel was
`tokenizers-0.22.2-cp39-abi3-win_amd64.whl`,
[PyPI SHA-256](https://pypi.org/project/tokenizers/0.22.2/#files)
`c9ea31edff2968b44a88f97d784c2f16dc0729b8b143ed004699ebca91f05c48`.
The [matching upstream Apache 2.0 LICENSE](https://github.com/huggingface/tokenizers/blob/v0.22.2/LICENSE)
establishes source provenance for review, not the complete notices of the
compiled extension or permission for the whole archive. Inspect the exact
wheel's contents separately.
