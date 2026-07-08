import sys
import os
from pathlib import Path

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
def _isolate_runtime_data(monkeypatch, request, tmp_path):
    """Keep SQLite-first tests away from the developer's real runtime data."""
    from config import constant

    data_dir = tmp_path / "data"
    watched_dir = data_dir / "watched"
    candidates_dir = data_dir / "candidates"
    cache_dir = data_dir / "cache"
    exports_dir = data_dir / "exports"
    logs_dir = data_dir / "logs"
    backup_dir = data_dir / "backups"

    monkeypatch.setattr(constant, "APP_DATA_DIR", str(data_dir))
    monkeypatch.setattr(constant, "WATCHED_DIR", str(watched_dir))
    monkeypatch.setattr(constant, "CANDIDATES_DIR", str(candidates_dir))
    monkeypatch.setattr(constant, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(constant, "EXPORTS_DIR", str(exports_dir))
    monkeypatch.setattr(constant, "LOGS_DIR", str(logs_dir))
    monkeypatch.setattr(constant, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(constant, "FILE_NAME", str(watched_dir / "titles.json"))
    monkeypatch.setattr(constant, "META_JSON", str(watched_dir / "meta.json"))
    monkeypatch.setattr(constant, "CANDIDATE_POOL_JSON", str(candidates_dir / "pool.json"))
    monkeypatch.setattr(constant, "CRITERIA_POOL_JSON", str(candidates_dir / "criteria.json"))

    from storage import profiles

    profiles.set_base_data_dir(data_dir)
    request.addfinalizer(lambda: profiles.set_base_data_dir(None))

    monkeypatch.delenv("WATCHBANE_UI_SCALE", raising=False)
    monkeypatch.delenv("WATCHBANE_INTERFACE_LANGUAGE", raising=False)
    monkeypatch.delenv("WATCHBANE_DATA_LANGUAGE", raising=False)

    import posters.cache as poster_cache_module

    poster_dir = cache_dir / "posters"
    monkeypatch.setattr(poster_cache_module, "DEFAULT_POSTER_CACHE_DIR", poster_dir)
    monkeypatch.setattr(poster_cache_module, "DEFAULT_POSTER_CACHE_JSON", poster_dir / "posters.json")
    monkeypatch.setattr(poster_cache_module, "DEFAULT_POSTER_IMAGES_DIR", poster_dir / "images")


@pytest.fixture(autouse=True)
def _block_real_poster_cache_writes(monkeypatch):
    """Prevent tests from overwriting the developer's data/cache/posters/posters.json."""
    from config import constant
    import posters.cache as poster_cache_module

    real_save = poster_cache_module.save_poster_cache

    def guarded_save(cache, path=None):
        if path is None:
            app_data_dir = Path(constant.APP_DATA_DIR).resolve()
            if "pytest" in app_data_dir.as_posix().lower():
                return real_save(cache, path=path)
            return poster_cache_module.DEFAULT_POSTER_CACHE_JSON
        return real_save(cache, path=path)

    monkeypatch.setattr(poster_cache_module, "save_poster_cache", guarded_save)
    monkeypatch.setattr("posters.download_images.save_poster_cache", guarded_save)
