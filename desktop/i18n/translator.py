"""Runtime translator for desktop interface strings."""

from __future__ import annotations

import os

from desktop.i18n.catalog import SUPPORTED_LANGUAGES, TRANSLATIONS
from desktop.settings.app_settings import APP_INTERFACE_LANGUAGE_ENV, load_app_settings, normalize_language


def get_interface_language() -> str:
    """Return the persisted interface language for this process."""
    env_value = os.environ.get(APP_INTERFACE_LANGUAGE_ENV)
    if env_value not in (None, ""):
        return normalize_language(env_value)
    return normalize_language(load_app_settings().interface_language)


def translate(key: str, *, interface_language: str | None = None, **kwargs) -> str:
    """Translate an interface string key with safe ru/key fallback."""
    language = normalize_language(interface_language or get_interface_language())
    template = TRANSLATIONS.get(language, {}).get(key)
    if template is None:
        template = TRANSLATIONS["ru"].get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return template
    return template


def tr(key: str, **kwargs) -> str:
    """Translate using the current process interface language."""
    return translate(key, **kwargs)
