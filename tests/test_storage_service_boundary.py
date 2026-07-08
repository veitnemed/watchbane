from __future__ import annotations

from pathlib import Path


def test_app_core_storage_does_not_import_sqlite_internals() -> None:
    source = Path("app/core/storage.py").read_text(encoding="utf-8")

    assert "storage.sqlite" not in source
    assert "action_repository" not in source


def test_poster_cache_does_not_import_sqlite_internals() -> None:
    source = Path("posters/cache.py").read_text(encoding="utf-8")

    assert "storage.sqlite" not in source
    assert "poster_repository" not in source


def test_app_core_storage_delegates_candidate_actions(monkeypatch) -> None:
    from app.core import storage as app_storage

    calls = []

    monkeypatch.setattr(app_storage.storage_actions, "add_to_watchlist", lambda candidate: calls.append(candidate) or {"ok": True})

    assert app_storage.add_to_watchlist({"title": "Dark"}) == {"ok": True}
    assert calls == [{"title": "Dark"}]
