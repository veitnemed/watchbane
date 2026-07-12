"""Per-runtime single-instance guard for the desktop application."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QLockFile
from PyQt6.QtWidgets import QMessageBox

from config import constant


LOCK_FILE_NAME = "watchbane.instance.lock"
STALE_LOCK_TIMEOUT_MS = 10_000


class SingleInstanceGuard:
    """Hold an OS-backed Qt lock for one active Watchbane runtime directory."""

    def __init__(self, runtime_dir: str | Path | None = None) -> None:
        root = Path(runtime_dir) if runtime_dir is not None else Path(constant.APP_DATA_DIR)
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / LOCK_FILE_NAME
        self._lock = QLockFile(str(self.path))
        self._lock.setStaleLockTime(STALE_LOCK_TIMEOUT_MS)
        self._acquired = False

    def acquire(self) -> bool:
        if self._acquired:
            return True
        self._acquired = bool(self._lock.tryLock(0))
        return self._acquired

    def release(self) -> None:
        if not self._acquired:
            return
        self._lock.unlock()
        self._acquired = False


def show_already_running_warning() -> None:
    QMessageBox.warning(
        None,
        "Watchbane",
        "Watchbane уже запущен для этого профиля.\n\n"
        "Watchbane is already running for this profile.",
    )
