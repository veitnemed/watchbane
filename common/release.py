"""Canonical public release identity for Watchbane and its recommendation engine."""

from __future__ import annotations

APP_VERSION = "0.1.1-alpha.1"
APP_RELEASE_TAG = f"v{APP_VERSION}"
APP_RELEASE_NAME = "Open Route"
APP_NAME = "Watchbane"
APP_DISPLAY_NAME = f"{APP_NAME} {APP_VERSION} — {APP_RELEASE_NAME}"

RECOMMENDATION_ENGINE_NAME = "ReDeck"
RECOMMENDATION_ENGINE_VERSION = "0.1.0"
RECOMMENDATION_ENGINE_DISPLAY_NAME = (
    f"{RECOMMENDATION_ENGINE_NAME} v{RECOMMENDATION_ENGINE_VERSION}"
)


def release_signature(*, include_name: bool = True) -> str:
    """Return the compact public version signature used by desktop surfaces."""
    app = APP_DISPLAY_NAME if include_name else f"{APP_NAME} {APP_VERSION}"
    return f"{app} · {RECOMMENDATION_ENGINE_DISPLAY_NAME}"


__all__ = [
    "APP_DISPLAY_NAME",
    "APP_NAME",
    "APP_RELEASE_NAME",
    "APP_RELEASE_TAG",
    "APP_VERSION",
    "RECOMMENDATION_ENGINE_DISPLAY_NAME",
    "RECOMMENDATION_ENGINE_NAME",
    "RECOMMENDATION_ENGINE_VERSION",
    "release_signature",
]
