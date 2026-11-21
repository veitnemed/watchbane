from functools import partial
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from candidates import title_state_service as state
from candidates.models.action_errors import CandidateActionIdentityConflict
from storage.sqlite import action_repository as repo
from storage.sqlite.connection import connect


def card(imdb, **extra):
    return dict(title="Общее имя", year=2020, media_type="movie", imdb_id=imdb, **extra)


def raw(path):
    return {action: repo.load_candidate_actions_dict(action, path=path)
            for action in (repo.ACTION_WATCHLIST, repo.ACTION_HIDDEN)}


@pytest.mark.parametrize("seed", [state.add_to_watchlist, state.hide_candidate])
@pytest.mark.parametrize("write", [state.add_to_watchlist, state.hide_candidate])
def test_conflicting_write_preserves_state_date_and_metadata(tmp_path, seed, write):
    db = tmp_path / "test.sqlite3"
    original = card("tt11", overview="Preserve me")
    seed(original, path=db)
    before = raw(db)
    with pytest.raises(CandidateActionIdentityConflict):
        write(card("tt22"), path=db)
    assert raw(db) == before
    assert state.get_title_state(card("tt22"), path=db) == state.STATE_AVAILABLE


def test_same_unknown_and_typed_promotion_remain_supported(tmp_path):
    db = tmp_path / "test.sqlite3"
    key = state.add_to_watchlist(card(None, overview="Original"), path=db)["identity"]
    first = raw(db)[repo.ACTION_WATCHLIST][key]
    state.add_to_watchlist(card("tt11"), path=db)
    enriched = raw(db)[repo.ACTION_WATCHLIST][key]
    assert enriched["candidate"]["imdb_id"] == "tt11"
    assert enriched["candidate"]["overview"] == "Original"
    assert enriched["added_at"] == first["added_at"]
    typed = dict(card("tt11", tmdb_id=18), title="Other spelling")
    new_key = state.add_to_watchlist(typed, path=db)["identity"]
    assert set(raw(db)[repo.ACTION_WATCHLIST]) == {new_key}
    assert raw(db)[repo.ACTION_WATCHLIST][new_key]["added_at"] == first["added_at"]
    state.hide_candidate(typed, path=db)
    assert not raw(db)[repo.ACTION_WATCHLIST]
    assert state.get_title_state(typed, path=db) == state.STATE_HIDDEN


def test_untyped_same_id_retag_remains_supported(tmp_path):
    db = tmp_path / "test.sqlite3"
    state.add_to_watchlist(card("tt11"), path=db)
    state.hide_candidate(card("tt11"), path=db)
    assert not raw(db)[repo.ACTION_WATCHLIST]
    assert state.get_title_state(card("tt11"), path=db) == state.STATE_HIDDEN


def test_noncanonical_conflict_is_not_deleted_and_failed_publish_rolls_back(tmp_path):
    db = tmp_path / "test.sqlite3"
    bare = "общее имя|2020"
    legacy = {"candidate": card("tt11"), "added_at": "2025-01-01T00:00:00Z"}
    repo.save_candidate_actions_dict(repo.ACTION_WATCHLIST, {bare: legacy}, path=db)
    state.hide_candidate(card("tt22"), path=db)
    assert raw(db)[repo.ACTION_WATCHLIST] == {bare: legacy}

    conn = connect(db)
    try:
        conn.execute("""CREATE TRIGGER broken BEFORE INSERT ON candidate_actions
        BEGIN SELECT RAISE(ABORT, 'test rollback'); END""")
    finally:
        conn.close()
    before = raw(db)
    with pytest.raises(sqlite3.IntegrityError, match="test rollback"):
        state.add_to_watchlist(card("tt22"), path=db)
    assert raw(db) == before


def test_qt_legacy_hide_paths_preserve_rows_and_present_failure(tmp_path, qapp, monkeypatch):
    from PyQt6.QtWidgets import QLabel, QWidget
    from desktop.candidates import list_actions
    from desktop.watched.tab import WatchedTabView

    db = tmp_path / "test.sqlite3"
    state.add_to_watchlist(card("tt11"), path=db)
    before = raw(db)
    hide = partial(state.hide_candidate, path=db)
    status = QLabel()
    watched = SimpleNamespace(_current_action_candidate=lambda: card("tt22"),
                              _state_service=SimpleNamespace(hide_candidate=hide),
                              _show_status=lambda message, _: status.setText(message),
                              _notify_entries_changed=Mock())
    WatchedTabView._apply_candidate_state_action(watched, "hidden")
    assert status.text().startswith("Действие не сохранено")
    watched._notify_entries_changed.assert_not_called()

    warning = Mock()
    monkeypatch.setattr(list_actions.QMessageBox, "warning", warning)
    selected = card("tt22")
    candidate = SimpleNamespace(_selected_candidate=selected, _widget=QWidget(),
                                _service=SimpleNamespace(hide_candidate=hide),
                                _log_search_action=Mock())
    list_actions.CandidateListActionsMixin._hide_selected_candidate(candidate)
    assert warning.call_args.args[2].startswith("Действие не сохранено")
    assert candidate._selected_candidate is selected
    candidate._log_search_action.assert_not_called()
    assert raw(db) == before


@pytest.mark.parametrize("command", ["1", "2"])
def test_console_reports_conflict_not_success(tmp_path, monkeypatch, capsys, command):
    from ui.console import search_menu

    db = tmp_path / "test.sqlite3"
    state.add_to_watchlist(card("tt11"), path=db)
    before = raw(db)
    monkeypatch.setattr("builtins.input", lambda _: "1")
    monkeypatch.setattr(search_menu.request, "loop_input", lambda **kw: command)
    monkeypatch.setattr(search_menu.candidate_service, "add_candidate_to_watchlist",
                        partial(state.add_to_watchlist, path=db))
    monkeypatch.setattr(search_menu.candidate_service, "hide_candidate",
                        partial(state.hide_candidate, path=db))
    search_menu.open_candidate_result_actions([card("tt22")])
    stdout = capsys.readouterr().out
    assert "Действие не сохранено" in stdout
    assert "Добавлено в" not in stdout and "Кандидат скрыт" not in stdout
    assert raw(db) == before
