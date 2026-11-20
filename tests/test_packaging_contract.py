from pathlib import Path, PurePosixPath
from runpy import run_path
from types import SimpleNamespace


def test_frozen_story_bundle_preserves_all_known_runtime_data_paths() -> None:
    def analysis(_scripts, **kwargs):
        return SimpleNamespace(**(kwargs | dict(pure=[], scripts=[], datas=kwargs["datas"])))

    result = run_path(
        "watchbane.spec",
        init_globals={
            "Analysis": analysis,
            "PYZ": lambda *_args, **_kwargs: None,
            "EXE": lambda *_args, **_kwargs: None,
            "COLLECT": lambda *_args, **_kwargs: None,
        },
    )
    datas = result["a"].datas
    source_targets = {source: PurePosixPath(destination) / Path(source).name for source, destination in datas}
    for path in (
        "desktop/images/story_ticket.svg",
        "candidates/search/title_aliases.json",
    ):
        assert Path(path).is_file()
        assert source_targets[path] == PurePosixPath(path)
    for source, _destination in datas:
        path = Path(source)
        assert path.exists()
        assert path.parts[0] in {"desktop", "candidates", "scripts"}
        for item in (*path.rglob("*"), path) if path.is_dir() else (path,):
            assert not item.is_symlink()
            assert item.suffix.lower() not in {".sqlite3", ".db", ".jsonl", ".onnx", ".env", ".bin"}


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
    bootstrap_source = Path("desktop/shell/bootstrap.py").read_text(encoding="utf-8")
    spec_source = Path("watchbane.spec").read_text(encoding="utf-8")

    assert '"desktop.analytics.charts"' not in source
    assert '"desktop.analytics.constants"' not in source
    assert "QtWebEngine" not in bootstrap_source
    assert "QtWebEngine" not in spec_source
    assert "collect_all" not in spec_source


def test_official_build_script_requires_onedir_executable() -> None:
    source = Path("tools/build_desktop.ps1").read_text(encoding="utf-8")

    assert "$Python -m PyInstaller --noconfirm --clean watchbane.spec" in source
    assert '"dist\\Watchbane"' in source
    assert '"Watchbane.exe"' in source
    assert r"_internal\desktop\images\story_ticket.svg" in source
    assert r"_internal\candidates\search\title_aliases.json" in source
    assert "-PathType Leaf" in source
    assert "Onedir build did not produce" in source
    assert "disable_windowed_traceback=True" in Path("watchbane.spec").read_text(encoding="utf-8")
