# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


webengine_datas, webengine_binaries, webengine_hiddenimports = collect_all(
    "PyQt6.QtWebEngineCore"
)

a = Analysis(
    ["start_app.py"],
    pathex=[],
    binaries=webengine_binaries,
    datas=[("desktop/images", "desktop/images"), *webengine_datas],
    hiddenimports=webengine_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
