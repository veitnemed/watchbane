"""JSONL event log for normal desktop GUI sessions."""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any


from config import constant


DEFAULT_GUI_LOG_DIR = Path(constant.LOGS_DIR) / "reports"
GUI_EVENT_LOG_ENV = "SERIES_LIST_GUI_EVENT_LOG"
_LOCK = Lock()
_SESSION_LOG_PATH: Path | None = None
_SESSION_ENABLED = False


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _session_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def start_gui_event_log(log_dir: str | Path | None = None) -> Path:
    """Create a JSONL event log for the current GUI process."""
    global _SESSION_ENABLED, _SESSION_LOG_PATH
    output_dir = Path(DEFAULT_GUI_LOG_DIR if log_dir is None else log_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        _SESSION_ENABLED = True
        if _SESSION_LOG_PATH is None:
            _SESSION_LOG_PATH = output_dir / f"{_session_stamp()}_gui_session.jsonl"
    log_event("app.start", argv=sys.argv, pid=os.getpid())
    return _SESSION_LOG_PATH


def gui_event_log_enabled() -> bool:
    value = os.environ.get(GUI_EVENT_LOG_ENV, "")
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def start_gui_event_log_if_enabled(log_dir: str | Path | None = None) -> Path | None:
    if gui_event_log_enabled() is False:
        return None
    try:
        return start_gui_event_log(log_dir)
    except OSError:
        return None


def log_event(event: str, **fields) -> None:
    """Append one event to the current GUI session log."""
    global _SESSION_ENABLED
    if _SESSION_ENABLED is False or _SESSION_LOG_PATH is None:
        return
    payload = {
        "at": _now_iso(),
        "event": event,
        **{str(key): _clean(value) for key, value in fields.items()},
    }
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    try:
        with _LOCK:
            with _SESSION_LOG_PATH.open("a", encoding="utf-8") as file:
                file.write(line + "\n")
    except OSError:
        _SESSION_ENABLED = False


def log_exception(event: str, error: BaseException, **fields) -> None:
    log_event(
        event,
        error_type=type(error).__name__,
        error_message=str(error),
        traceback=traceback.format_exc(),
        **fields,
    )
