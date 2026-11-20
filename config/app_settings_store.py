"""Backend adapter for desktop app settings persistence."""

from __future__ import annotations


def load_sqlite_settings_dict() -> dict:
    from storage.sqlite.settings_repository import load_settings_dict

    return load_settings_dict()


def save_sqlite_settings_dict(payload: dict) -> None:
    from storage.sqlite.settings_repository import set_setting

    if isinstance(payload, dict) is False:
        return
    for key, value in payload.items():
        set_setting(str(key), value)



class ProfileSetting:
    """One setting bound to the profile which created its owner."""

    def __init__(self, key: str):
        from storage.sqlite.connection import get_db_path

        self._key = key
        self._path = get_db_path()

    def read(self):
        from storage.sqlite.settings_repository import get_setting

        return get_setting(self._key, path=self._path)

    def write(self, value) -> None:
        from storage.sqlite.settings_repository import set_setting

        set_setting(self._key, value, path=self._path)
