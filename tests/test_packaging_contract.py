import importlib.util
import json
import sys
from pathlib import Path, PurePosixPath
from runpy import run_path
from types import ModuleType, SimpleNamespace

import pytest


def _analyze_spec():
    def analysis(_scripts, **kwargs):
        return SimpleNamespace(**(kwargs | dict(pure=[], scripts=[], datas=kwargs["datas"])))

    return run_path(
        "watchbane.spec",
        init_globals={
            "Analysis": analysis,
            "PYZ": lambda *_args, **_kwargs: None,
            "EXE": lambda *_args, **_kwargs: None,
            "COLLECT": lambda *_args, **_kwargs: None,
        },
    )["a"]


def test_frozen_story_bundle_preserves_all_known_runtime_data_paths(monkeypatch) -> None:
    monkeypatch.delenv("WATCHBANE_BUNDLE_PROFILE", raising=False)
    datas = _analyze_spec().datas
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


def test_lexical_build_excludes_semantic_packages_even_on_a_dirty_builder(monkeypatch) -> None:
    monkeypatch.delenv("WATCHBANE_BUNDLE_PROFILE", raising=False)
    spec = _analyze_spec()
    assert spec.excludes == ["numpy", "onnxruntime", "tokenizers"]
    assert spec.hiddenimports == spec.binaries == []


def test_semantic_build_includes_libraries_not_a_catalog_or_model(monkeypatch) -> None:
    monkeypatch.setenv("WATCHBANE_BUNDLE_PROFILE", "semantic")
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    hooks = ModuleType("PyInstaller.utils.hooks")
    hooks.collect_dynamic_libs = lambda package: [(f"{package}/capi/providers.dll", f"{package}/capi")]
    monkeypatch.setitem(sys.modules, hooks.__name__, hooks)
    semantic = _analyze_spec()
    assert semantic.excludes == []
    assert semantic.hiddenimports == ["numpy", "onnxruntime", "tokenizers"]
    assert semantic.binaries == [("onnxruntime/capi/providers.dll", "onnxruntime/capi")]
    monkeypatch.setenv("WATCHBANE_BUNDLE_PROFILE", "lexical")
    assert semantic.datas == _analyze_spec().datas


def test_semantic_build_fails_before_analysis_if_optional_packages_are_absent(monkeypatch) -> None:
    monkeypatch.setenv("WATCHBANE_BUNDLE_PROFILE", "semantic")
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None if name == "tokenizers" else object())
    with pytest.raises(RuntimeError, match="tokenizers.*requirements-story.txt"):
        _analyze_spec()


def test_spec_rejects_unknown_bundle_profile(monkeypatch) -> None:
    monkeypatch.setenv("WATCHBANE_BUNDLE_PROFILE", "semnatic")
    with pytest.raises(ValueError, match="must be lexical or semantic"):
        _analyze_spec()


def test_optional_probe_before_gui_reports_missing_library_without_a_model(monkeypatch, tmp_path) -> None:
    from candidates import story_runtime_probe

    def missing(name):
        raise ModuleNotFoundError(name, name=name)

    monkeypatch.setattr(story_runtime_probe, "import_module", missing)
    output = tmp_path / "semantic.json"
    monkeypatch.setattr(sys, "argv", ["Watchbane.exe", "--check-semantic-runtime", str(output)])
    with pytest.raises(SystemExit) as exit:
        run_path("start_app.py", run_name="__main__")
    assert exit.value.code == 1
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "status": "library_missing",
        "library": "numpy",
        "error_type": "ModuleNotFoundError",
        "model_tested": False,
    }


def test_probe_distinguishes_broken_installed_library_from_optional_missing(monkeypatch) -> None:
    from candidates import story_runtime_probe

    def broken(name):
        raise ModuleNotFoundError("Module in DLL wrapper missing", name="compiled_dependency")

    monkeypatch.setattr(story_runtime_probe, "import_module", broken)
    assert story_runtime_probe.check_runtime()["status"] == "runtime_error"


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
