"""Backend adapter for desktop app settings persistence."""

from __future__ import annotations


def is_sqlite_settings_backend() -> bool:
    from storage.backend import is_sqlite_backend

    return is_sqlite_backend()


def load_sqlite_settings_dict() -> dict:
    from storage.sqlite.settings_repository import load_settings_dict

    return load_settings_dict()


def save_sqlite_settings_dict(payload: dict) -> None:
    from storage.sqlite.settings_repository import save_settings_dict

    save_settings_dict(payload)

