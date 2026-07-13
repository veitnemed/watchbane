# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["start_app.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("desktop/images/logos", "desktop/images/logos"),
        (
            "desktop/images/logos_for_start_select_menu",
            "desktop/images/logos_for_start_select_menu",
        ),
        ("desktop/images/user_rating_not_for_me.svg", "desktop/images"),
        ("desktop/images/user_rating_ok.svg", "desktop/images"),
        ("desktop/images/user_rating_top.svg", "desktop/images"),
    ],
    hiddenimports=[],
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
