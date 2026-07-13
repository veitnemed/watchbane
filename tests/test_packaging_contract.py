from pathlib import Path


def test_onedir_spec_bundles_only_runtime_image_assets() -> None:
    source = Path("watchbane.spec").read_text(encoding="utf-8")

    assert "COLLECT(" in source
    assert 'name="Watchbane"' in source
    assert '"desktop/images/logos"' in source
    assert '"desktop/images/logos_for_start_select_menu"' in source
    assert '"desktop/images/user_rating_top.svg"' in source
    assert '"desktop/images", "desktop/images"' not in source
    assert "ui_9" not in source


def test_packaged_startup_does_not_dynamically_require_retired_analytics() -> None:
    source = Path("desktop/theme/ui_modules.py").read_text(encoding="utf-8")

    assert '"desktop.analytics.charts"' not in source
    assert '"desktop.analytics.constants"' not in source


def test_official_build_script_requires_onedir_executable() -> None:
    source = Path("tools/build_desktop.ps1").read_text(encoding="utf-8")

    assert "py -m PyInstaller --noconfirm --clean watchbane.spec" in source
    assert '"dist\\Watchbane\\Watchbane.exe"' in source
    assert "Onedir build did not produce" in source
    assert "disable_windowed_traceback=True" in Path("watchbane.spec").read_text(encoding="utf-8")
