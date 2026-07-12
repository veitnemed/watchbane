from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QListWidget, QPushButton, QTabBar


def _entry(key: str, title: str):
    movie = {"main_info": {"title": title, "year": 2024, "media_type": "movie", "user_score": 8.0}}
    card = {"title": title, "year": 2024, "media_type": "movie", "user_score": 8.0, "genres": []}
    return (key, movie, card)


def _candidate(title: str) -> dict:
    return {
        "pool_entry_key": title.casefold().replace(" ", "-") + "|2024|movie",
        "title": title,
        "year": 2024,
        "media_type": "movie",
        "tmdb_score": 7.8,
        "is_searchable": True,
        "is_complete": True,
    }


def _action_entry(candidate: dict):
    key = f"__candidate__{candidate['pool_entry_key']}"
    entry = _entry(key, candidate["title"])
    return entry, {key: candidate}


def _listed_titles(widget: QListWidget) -> list[str]:
    return [
        widget.item(row).data(Qt.ItemDataRole.UserRole)[2]["title"]
        for row in range(widget.count())
    ]


class FakeStateService:
    def __init__(self, states: dict[str, list[dict]], watched_entries: list[tuple]) -> None:
        self.states = states
        self.watched_entries = watched_entries
        self.calls: list[tuple[str, str]] = []

    def _remove(self, candidate: dict) -> None:
        for candidates in self.states.values():
            candidates[:] = [item for item in candidates if item["pool_entry_key"] != candidate["pool_entry_key"]]

    def restore_candidate(self, candidate: dict) -> dict:
        self.calls.append(("restore", candidate["title"]))
        self._remove(candidate)
        return {"ok": True, "state": "available"}

    def hide_candidate(self, candidate: dict) -> dict:
        self.calls.append(("hidden", candidate["title"]))
        self._remove(candidate)
        self.states["hidden"].append(candidate)
        return {"ok": True, "state": "hidden"}

    def mark_watched(self, candidate: dict) -> dict:
        self.calls.append(("watched", candidate["title"]))
        self._remove(candidate)
        key = candidate["title"]
        self.watched_entries.append(_entry(key, candidate["title"]))
        return {"ok": True, "state": "watched", "dataset_key": key}


def _build_library(qtbot, monkeypatch, *, empty: bool = False):
    from desktop.watched import tab as watched_tab_module

    watched_entries = [] if empty else [_entry("watched-alpha", "Watched Alpha")]
    states = {
        "watchlist": [] if empty else [_candidate("Saved Beta")],
        "hidden": [] if empty else [_candidate("Hidden Gamma")],
    }
    state_service = FakeStateService(states, watched_entries)

    def load_actions(action: str, *, data_language: str = "ru"):
        entries = []
        candidates_by_key = {}
        for candidate in states[action]:
            entry, mapping = _action_entry(deepcopy(candidate))
            entries.append(entry)
            candidates_by_key.update(mapping)
        return entries, candidates_by_key

    monkeypatch.setattr(watched_tab_module, "load_watched_entries", lambda **_kwargs: list(watched_entries))
    view = watched_tab_module.WatchedTabView(
        action_entries_loader=load_actions,
        state_service=state_service,
    )
    qtbot.addWidget(view.widget)
    view.widget.show()
    return view, state_service


def test_watched_tab_hides_detail_panel_in_compact_layout(qtbot, monkeypatch) -> None:
    from desktop.theme.shell_layout import WATCHED_DETAIL_COLLAPSE_WIDTH_PX

    view, _state = _build_library(qtbot, monkeypatch)
    for compact in (True, False, True, False):
        width = (
            WATCHED_DETAIL_COLLAPSE_WIDTH_PX - 1
            if compact
            else 1280
        )
        view.widget.resize(width, 800)

        qtbot.waitUntil(lambda: view._is_compact_layout is compact)
        assert view._right_panel.isHidden() is compact
        assert view._splitter.handle(1).isHidden() is compact
        if compact:
            assert view._left_panel.width() >= view._splitter.width() - 1
        else:
            assert view._right_panel.isVisible()


def test_library_sections_show_watched_saved_and_hidden(qtbot, monkeypatch) -> None:
    view, _state = _build_library(qtbot, monkeypatch)
    tabs = view.widget.findChild(QTabBar, "librarySectionTabs")
    listing = view.widget.findChild(QListWidget, "watchedList")

    assert tabs is not None and listing is not None
    assert [tabs.tabText(index) for index in range(tabs.count())] == ["Просмотрено", "Отложено", "Скрыто"]
    assert _listed_titles(listing) == ["Watched Alpha"]
    tabs.setCurrentIndex(1)
    assert _listed_titles(listing) == ["Saved Beta"]
    tabs.setCurrentIndex(2)
    assert _listed_titles(listing) == ["Hidden Gamma"]


def test_hidden_restore_removes_hidden_state(qtbot, monkeypatch) -> None:
    view, state = _build_library(qtbot, monkeypatch)
    tabs = view.widget.findChild(QTabBar, "librarySectionTabs")
    listing = view.widget.findChild(QListWidget, "watchedList")
    tabs.setCurrentIndex(2)
    restore = view.widget.findChild(QPushButton, "libraryPrimaryActionButton")

    assert restore is not None and restore.isEnabled()
    restore.click()

    assert state.calls[-1] == ("restore", "Hidden Gamma")
    assert _listed_titles(listing) == []


def test_saved_to_watched_moves_between_sections(qtbot, monkeypatch) -> None:
    view, state = _build_library(qtbot, monkeypatch)
    tabs = view.widget.findChild(QTabBar, "librarySectionTabs")
    listing = view.widget.findChild(QListWidget, "watchedList")
    tabs.setCurrentIndex(1)
    watched = view.widget.findChild(QPushButton, "libraryPrimaryActionButton")

    watched.click()

    assert state.calls[-1] == ("watched", "Saved Beta")
    assert tabs.currentIndex() == 0
    assert "Saved Beta" in _listed_titles(listing)


def test_search_filters_every_library_section(qtbot, monkeypatch) -> None:
    view, _state = _build_library(qtbot, monkeypatch)
    tabs = view.widget.findChild(QTabBar, "librarySectionTabs")
    listing = view.widget.findChild(QListWidget, "watchedList")
    search = view.widget.findChild(QLineEdit, "watchedSearch")

    for index, query, expected in (
        (0, "alpha", ["Watched Alpha"]),
        (1, "beta", ["Saved Beta"]),
        (2, "gamma", ["Hidden Gamma"]),
    ):
        search.clear()
        tabs.setCurrentIndex(index)
        search.setText(query)
        qtbot.waitUntil(lambda expected=expected: _listed_titles(listing) == expected)


def test_empty_library_sections_are_stable(qtbot, monkeypatch) -> None:
    view, _state = _build_library(qtbot, monkeypatch, empty=True)
    tabs = view.widget.findChild(QTabBar, "librarySectionTabs")
    listing = view.widget.findChild(QListWidget, "watchedList")

    for index in range(3):
        tabs.setCurrentIndex(index)
        assert listing.count() == 0


def test_library_section_labels_are_localized_without_mojibake() -> None:
    from desktop.i18n import translate

    for language, expected in (
        ("ru", ("Просмотрено", "Отложено", "Скрыто")),
        ("en", ("Watched", "Saved", "Hidden")),
    ):
        actual = tuple(
            translate(key, interface_language=language)
            for key in ("library.section.watched", "library.section.saved", "library.section.hidden")
        )
        assert actual == expected
        assert all("Р" not in label and "С" not in label for label in actual if language == "en")


def test_library_adapter_reads_persisted_saved_and_hidden_states(tmp_path) -> None:
    from candidates import title_state_service
    from desktop.watched.library_states import load_action_library_entries

    db_path = tmp_path / "library.sqlite3"
    saved = _candidate("Saved Persisted")
    hidden = _candidate("Hidden Persisted")
    title_state_service.add_to_watchlist(saved, path=db_path)
    title_state_service.hide_candidate(hidden, path=db_path)

    saved_entries, _saved_candidates = load_action_library_entries("watchlist", path=db_path)
    hidden_entries, _hidden_candidates = load_action_library_entries("hidden", path=db_path)

    assert [entry[2]["title"] for entry in saved_entries] == ["Saved Persisted"]
    assert [entry[2]["title"] for entry in hidden_entries] == ["Hidden Persisted"]
