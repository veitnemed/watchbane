"""Tests for the public title_resolve facade."""

from __future__ import annotations

import builtins
import importlib
import sys


def test_importing_title_resolve_does_not_require_kp_or_imdb_modules(monkeypatch) -> None:
    for module_name in [
        "dataset.title_resolve",
        "apis.kp_api",
        "apis.imdb_sql",
    ]:
        sys.modules.pop(module_name, None)

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"apis.kp_api", "apis.imdb_sql"}:
            raise AssertionError(f"{name} must not be imported by dataset.title_resolve")
        if name == "apis" and any(item in {"kp_api", "imdb_sql"} for item in fromlist or ()):
            raise AssertionError(f"{name}.{fromlist} must not be imported by dataset.title_resolve")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    module = importlib.import_module("dataset.title_resolve")

    assert hasattr(module, "resolve_title_data_for_add")
    assert hasattr(module, "build_tmdb_add_defaults")
    assert "api" not in module.__all__
    assert "sql_search" not in module.__all__
