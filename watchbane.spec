# -*- mode: python ; coding: utf-8 -*-

import os
from importlib.util import find_spec

profile = os.environ.get("WATCHBANE_BUNDLE_PROFILE", "lexical")
if profile not in {"lexical", "semantic"}:
    raise ValueError("WATCHBANE_BUNDLE_PROFILE must be lexical or semantic")

semantic_modules = ["numpy", "onnxruntime", "tokenizers"]
semantic_binaries = []
if profile == "semantic":
    missing = [name for name in semantic_modules if find_spec(name) is None]
    if missing:
        raise RuntimeError(
            f"Missing semantic runtime modules: {', '.join(missing)}. "
            "Install requirements-story.txt in the build environment."
        )
    from PyInstaller.utils.hooks import collect_dynamic_libs

    # Keep the package-relative destinations for the ORT provider DLLs.
    # NumPy and tokenizers are handled by PyInstaller's extension analysis/hooks.
    semantic_binaries = collect_dynamic_libs("onnxruntime")

a = Analysis(
    ["start_app.py"],
    pathex=[],
    binaries=semantic_binaries,
    datas=[
        ("desktop/images/logos", "desktop/images/logos"),
        (
            "desktop/images/logos_for_start_select_menu",
            "desktop/images/logos_for_start_select_menu",
        ),
        ("desktop/images/user_rating_not_for_me.svg", "desktop/images"),
        ("desktop/images/user_rating_ok.svg", "desktop/images"),
        ("desktop/images/user_rating_top.svg", "desktop/images"),
        ("desktop/images/story_ticket.svg", "desktop/images"),
        ("candidates/search/title_aliases.json", "candidates/search"),
        ("scripts/tmdb-network-diagnose.ps1", "scripts"),
        ("scripts/tmdb-network-compare.ps1", "scripts"),
        ("scripts/tmdb-dns-recovery.ps1", "scripts"),
        ("scripts/tmdb-hosts-override.ps1", "scripts"),
    ],
    hiddenimports=semantic_modules if profile == "semantic" else [],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=semantic_modules if profile == "lexical" else [],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Watchbane",
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="tools/windows_version_info.txt",
    icon=["desktop/images/logos/main_icon.ico"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Watchbane",
)
