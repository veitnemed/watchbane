"""Safe user-facing handling for local runtime write failures."""

from __future__ import annotations

import errno
import sqlite3

from desktop.i18n import tr


_SQLITE_WRITE_MARKERS = (
    "attempt to write a readonly database",
    "database or disk is full",
    "disk i/o error",
    "unable to open database file",
    "database is locked",
    "database table is locked",
)


def is_storage_write_error(error: BaseException | str) -> bool:
    if isinstance(error, (PermissionError, IsADirectoryError)):
        return True
    if isinstance(error, OSError) and error.errno in {
        errno.EACCES,
        errno.EBUSY,
        errno.ENOSPC,
        errno.EROFS,
    }:
        return True
    message = str(error).casefold()
    return any(marker in message for marker in _SQLITE_WRITE_MARKERS)


def storage_write_error_message() -> str:
    return tr("storage.error.write_unavailable")
