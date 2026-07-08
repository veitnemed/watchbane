from __future__ import annotations

from storage import backend


def test_storage_backend_defaults_to_json(monkeypatch) -> None:
    monkeypatch.delenv(backend.ENV_STORAGE_BACKEND, raising=False)

    assert backend.get_storage_backend() == backend.BACKEND_JSON
    assert backend.is_sqlite_backend() is False


def test_storage_backend_allows_sqlite_override(monkeypatch) -> None:
    monkeypatch.setenv(backend.ENV_STORAGE_BACKEND, "sqlite")

    assert backend.get_storage_backend() == backend.BACKEND_SQLITE
    assert backend.is_sqlite_backend() is True


def test_storage_backend_invalid_value_falls_back_to_json(monkeypatch) -> None:
    monkeypatch.setenv(backend.ENV_STORAGE_BACKEND, "postgres")

    assert backend.get_storage_backend() == backend.BACKEND_JSON

