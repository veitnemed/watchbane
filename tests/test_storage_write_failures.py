from __future__ import annotations

import errno
import sqlite3

import pytest

from candidates import title_state_service
from desktop.storage_errors import is_storage_write_error


@pytest.mark.parametrize(
    "error",
    (
        PermissionError("denied"),
        OSError(errno.ENOSPC, "no space"),
        OSError(errno.EROFS, "read only"),
        sqlite3.OperationalError("database or disk is full"),
        sqlite3.OperationalError("attempt to write a readonly database"),
        sqlite3.OperationalError("database is locked"),
        "unable to open database file",
    ),
)
def test_storage_write_errors_are_classified_without_exposing_paths(error) -> None:
    assert is_storage_write_error(error) is True


def test_unrelated_errors_are_not_misreported_as_disk_failures() -> None:
    assert is_storage_write_error(ValueError("bad payload")) is False
    assert is_storage_write_error("network timeout") is False


def test_failed_watched_transition_rolls_back_existing_action(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "runtime.sqlite3"
    candidate = {
        "title": "Atomic title",
        "year": 2024,
        "media_type": "movie",
        "tmdb_id": 700,
        "tmdb_score": 8.0,
        "tmdb_votes": 1000,
    }
    title_state_service.add_to_watchlist(candidate, path=db_path)
    real_clear = title_state_service._clear_candidate_actions

    def fail_after_clear(conn, value):
        real_clear(conn, value)
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(title_state_service, "_clear_candidate_actions", fail_after_clear)

    with pytest.raises(sqlite3.OperationalError, match="disk is full"):
        title_state_service.mark_watched(candidate, 3, path=db_path)

    assert title_state_service.get_title_state(candidate, path=db_path) == "watchlist"


def test_optional_gui_diagnostics_failure_disables_logging(monkeypatch, tmp_path) -> None:
    from diagnostics import gui_event_log

    monkeypatch.setattr(
        gui_event_log,
        "start_gui_event_log",
        lambda _path=None: (_ for _ in ()).throw(PermissionError("diagnostics denied")),
    )
    monkeypatch.setenv(gui_event_log.GUI_EVENT_LOG_ENV, "1")

    assert gui_event_log.start_gui_event_log_if_enabled(tmp_path) is None

    class UnwritableLog:
        def open(self, *_args, **_kwargs):
            raise OSError(errno.ENOSPC, "disk full")

    monkeypatch.setattr(gui_event_log, "_SESSION_ENABLED", True)
    monkeypatch.setattr(gui_event_log, "_SESSION_LOG_PATH", UnwritableLog())
    gui_event_log.log_event("test.event")
    assert gui_event_log._SESSION_ENABLED is False
