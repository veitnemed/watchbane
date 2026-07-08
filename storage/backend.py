"""Storage backend selection."""

from __future__ import annotations

import os


BACKEND_JSON = "json"
BACKEND_SQLITE = "sqlite"
ENV_STORAGE_BACKEND = "WATCHBANE_STORAGE_BACKEND"
_SUPPORTED_BACKENDS = {BACKEND_JSON, BACKEND_SQLITE}


def get_storage_backend() -> str:
    """Return the active storage backend, defaulting to legacy JSON."""
    value = os.environ.get(ENV_STORAGE_BACKEND, BACKEND_JSON)
    backend = str(value or "").strip().casefold()
    if backend in _SUPPORTED_BACKENDS:
        return backend
    return BACKEND_JSON


def is_sqlite_backend() -> bool:
    return get_storage_backend() == BACKEND_SQLITE

