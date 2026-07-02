from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QListWidget


def _entry(key: str, title: str, year: int = 2020):
    movie = {
        "main_info": {
            "title": title,
            "user_score": 8.0,
            "year": year,
            "country": "США",
        },
        "raw_scores": {"tmdb_score": 7.8, "tmdb_votes": 100, "tmdb_popularity": 10.0},
        "computed_scores": {"tmdb_score": 7.8, "tmdb_votes": 100, "tmdb_popularity": 10.0},
        "tags_vibe": {},
        "genre": {},
    }
    card = {
        "title": title,
        "year": year,
        "user_score": 8.0,
        "genres": [],
    }
    return (key, movie, card)


def _listed_titles(list_widget: QListWidget) -> list[str]:
    titles = []
    for row in range(list_widget.count()):
        entry = list_widget.item(row).data(Qt.ItemDataRole.UserRole)
        titles.append(entry[2]["title"])
    return titles


def test_watched_search_input_filters_visible_list(qtbot, monkeypatch) -> None:
    from desktop.watched import tab as watched_tab_module

    entries = [
        _entry("alpha", "Alpha Show"),
        _entry("beta", "Beta Match"),
        _entry("gamma", "Gamma Show"),
    ]
    monkeypatch.setattr(watched_tab_module, "load_watched_entries", lambda: list(entries))

    watched_tab = watched_tab_module.WatchedTabView()
    qtbot.addWidget(watched_tab.widget)

    search_input = watched_tab.widget.findChild(QLineEdit, "watchedSearch")
    list_widget = watched_tab.widget.findChild(QListWidget, "watchedList")

    assert search_input is not None
    assert list_widget is not None
    assert _listed_titles(list_widget) == ["Alpha Show", "Beta Match", "Gamma Show"]

    search_input.setText("beta")

    qtbot.waitUntil(lambda: _listed_titles(list_widget) == ["Beta Match"])
    assert watched_tab._debounced_search is not None
