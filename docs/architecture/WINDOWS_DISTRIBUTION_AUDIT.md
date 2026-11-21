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

## Release acceptance on desktop Windows

Отдельный [пилот первого самостоятельного запуска](../operations/STORY_FIRST_RUN_UX_ACCEPTANCE.md) проверяет понятность сценария для нового человека. Этот план не означает, что пилот уже пройден.

Use an already authorized clean Windows client. An enabled [Windows
Sandbox](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/)
is suitable for a disposable first-launch check. Windows 11 version 22H2 and
later preserve guest state across a reboot initiated inside Sandbox; closing
Sandbox still discards it. Prefer a clean VM snapshot for acceptance on a
specific desktop edition or for durable profile verification. Record the
actual edition, build and architecture; a Windows 11 result is not evidence
of Windows 10 support.

1. Download the exact candidate Windows archive through the intended
   recipient channel using its normal browser or download client, as a regular
   user under default security settings. A direct local copy is diagnostic
   only. Record browser receipt, warnings or blocks separately, then verify and
   record the SHA-256 and build commit if downloaded. Record the VC++ v14
   registration before starting; don't uninstall system runtimes to simulate a
   blank host. Use a fresh application profile without Python, seeded weights
   or imported user data. If sharing files with a VM, expose only the needed
   candidate and approved QA inputs, not a developer profile or credentials.
2. Record normal extraction or installation and first launch separately. Check
   the unmodified executable's signature and publisher, and record any
   [SmartScreen](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation),
   [Smart App Control](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview),
   UAC or other prompt, including whether it warned or blocked. Record missing
   runtimes, unexpected elevation or manual setup separately. Do not disable
   protections or bypass a block to pass acceptance. If launch is blocked,
   mark the app and E5 steps as not run, not as application failures. Hosted
   CI and private QA overlays are useful diagnostics, not substitutes.
3. With internet enabled, use the visible **Подключить поиск по смыслу…**
   control once and confirm the offered download. Check that E5 is shown as
   active after verification. No manual model path, Python install or API key
   should be required for the supported first-run flow.
4. Use an approved real catalog through the same route available to the
   recipient; don't silently preload a private QA dataset. Record its size,
   provenance, expected film and actual rank for a fixed Russian plot query.
   Save a result, close the app, start it again and verify that both E5 and the
   saved result persist. Record separately whether the second search also works
   offline. Capture the actual product UI and any failure steps.
5. Mark only the tested OS and distribution route as verified. A successful
   run doesn't authorize distribution: the exact downloadable archive and
   catalog still need the separate source and notice review above.

The explicit frozen E5 inference smoke reports, after inference, whether
selected v14 modules already visible in that process map to the PyInstaller
bundle's internal directory, the Windows directory, or another location.
The report contains only fixed DLL basenames and categories; it never loads a
candidate DLL for diagnosis or prints local paths. These are
[loaded-module observations](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getmodulehandlew),
not a dependency trace: only one handle is observed per basename, and the
observation does not establish which caller loaded it, which redistributable
is needed on a clean host, or permission to copy it.
