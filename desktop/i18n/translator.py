"""Runtime translator for desktop interface strings."""

from __future__ import annotations

from desktop.i18n.catalog import SUPPORTED_LANGUAGES, TRANSLATIONS
from desktop.settings.app_settings import load_app_settings, normalize_language


def get_interface_language() -> str:
    """Return the persisted interface language for this process."""
    return normalize_language(load_app_settings().interface_language)


def tr(key: str, **kwargs) -> str:
    """Translate an interface string key with safe ru/key fallback."""
    language = get_interface_language()
    template = TRANSLATIONS.get(language, {}).get(key)
    if template is None:
        template = TRANSLATIONS["ru"].get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return template
    return template
