"""Desktop interface i18n helpers."""

from desktop.i18n.catalog import SUPPORTED_LANGUAGES, TRANSLATIONS
from desktop.i18n.translator import get_interface_language, tr, translate

__all__ = [
    "SUPPORTED_LANGUAGES",
    "TRANSLATIONS",
    "get_interface_language",
    "tr",
    "translate",
]
