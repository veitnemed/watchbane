"""Desktop language context for new tabs and UI objects."""

from __future__ import annotations

from dataclasses import dataclass

from desktop.i18n import get_interface_language, translate
from desktop.settings.app_settings import (
    get_persisted_data_language,
    language_to_tmdb_locale,
    normalize_language,
)


@dataclass(frozen=True)
class DesktopLanguageContext:
    """Current interface/data language split for desktop UI construction."""

    interface_language: str
    data_language: str
    tmdb_locale: str

    def tr(self, key: str, **kwargs) -> str:
        """Translate an interface string without reading settings again."""
        return translate(key, interface_language=self.interface_language, **kwargs)


def load_desktop_language_context() -> DesktopLanguageContext:
    """Return the current desktop language context, including env overrides."""
    data_language = normalize_language(get_persisted_data_language())
    return DesktopLanguageContext(
        interface_language=normalize_language(get_interface_language()),
        data_language=data_language,
        tmdb_locale=language_to_tmdb_locale(data_language),
    )


__all__ = [
    "DesktopLanguageContext",
    "load_desktop_language_context",
]
