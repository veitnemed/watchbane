import sys
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture(autouse=True)
def _default_tests_to_legacy_json_backend(monkeypatch):
    """Keep legacy JSON-focused tests explicit after app default flips to SQLite."""
    monkeypatch.setenv("WATCHBANE_STORAGE_BACKEND", "json")


@pytest.fixture(autouse=True)
def _block_real_poster_cache_writes(monkeypatch):
    """Prevent tests from overwriting the developer's data/cache/posters/posters.json."""
    import posters.cache as poster_cache_module

    real_save = poster_cache_module.save_poster_cache

    def guarded_save(cache, path=None):
        if path is None:
            from storage.backend import is_sqlite_backend

            if is_sqlite_backend():
                return real_save(cache, path=path)
            return poster_cache_module.DEFAULT_POSTER_CACHE_JSON
        return real_save(cache, path=path)

    monkeypatch.setattr(poster_cache_module, "save_poster_cache", guarded_save)
    monkeypatch.setattr("posters.download_images.save_poster_cache", guarded_save)
