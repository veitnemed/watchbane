"""Persisted homonyms must not share the action target of a Collection card."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton

from candidates import title_state_service as states
from desktop.collection.view import CollectionView
from desktop.watched.tab import WatchedTabView


def make_candidate(tmdb_id, marker):
    return {
        "pool_entry_key": "два названия|2024|movie",
        "title": "Два названия",
        "media_type": "movie",
        "year": 2024,
        "tmdb_id": tmdb_id,
        "overview": f"Сюжет: {marker}.",
    }


def open_collection(qtbot):
    view = CollectionView(WatchedTabView())
    qtbot.addWidget(view.widget)
    view.widget.resize(1200, 850)
    view.widget.show()
    return view


def click(qtbot, widget):
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)


def cards(view):
    return view.cards.findChildren(QFrame, "collectionCard")


def test_collection_routes_each_saved_homonym_to_its_persisted_tmdb_identity(qtbot):
    titles = [make_candidate(12991, "первая история"), make_candidate(12992, "вторая история")]
    for item in titles:
        states.add_to_watchlist(item)

    view = open_collection(qtbot)
    assert len(cards(view)) == 2
    first, second = view.legacy._entries
    assert set(view.legacy._action_candidates_by_key) == {
        "__candidate__tmdb:movie:12991", "__candidate__tmdb:movie:12992",
    }
    by_id = {str(item["tmdb_id"]): item for item in titles}
    target = by_id[first[0].rsplit(":", 1)[1]]
    other = by_id[second[0].rsplit(":", 1)[1]]
    clicked_card = cards(view)[0]
    assert clicked_card.findChild(QLabel, "storyEvidence").text() == target["overview"]
    assert cards(view)[1].findChild(QLabel, "storyEvidence").text() == other["overview"]

    click(qtbot, next(b for b in clicked_card.findChildren(QPushButton) if b.text() == "Скрыть"))
    assert states.get_title_state(target) == states.STATE_HIDDEN
    assert states.get_title_state(other) == states.STATE_WATCHLIST

    view.widget.close()
    reopened = open_collection(qtbot)
    assert len(cards(reopened)) == 1
    assert cards(reopened)[0].findChild(QLabel, "storyEvidence").text() == other["overview"]
    click(qtbot, reopened.section_buttons["hidden"])
    assert len(cards(reopened)) == 1
    hidden_card = cards(reopened)[0]
    assert hidden_card.findChild(QLabel, "storyEvidence").text() == target["overview"]
    click(qtbot, next(b for b in hidden_card.findChildren(QPushButton) if b.text() == "Вернуть"))
    assert states.get_title_state(target) == states.STATE_AVAILABLE
    assert states.get_title_state(other) == states.STATE_WATCHLIST
    assert not cards(reopened)


def test_score_write_failure_keeps_card_and_reports_error(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog
    from app.use_cases import watched_library
    from dataset.models.results import UpdateRecordResult

    title = make_candidate(12993, "чужая запись не меняется")
    key = states.mark_watched(title, optional_user_score=3)["dataset_key"]
    view = open_collection(qtbot)
    click(qtbot, view.section_buttons["watched"])
    card = cards(view)[0]
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args, **kwargs: ("1", True))
    monkeypatch.setattr(watched_library, "update_user_score",
                        lambda *args: UpdateRecordResult(False, key, "error", "save_error", []))
    click(qtbot, next(button for button in card.findChildren(QPushButton) if button.text() == "Оценка"))
    assert "Не удалось сохранить оценку" in view.status.text()
    assert cards(view)[0] is card
    assert view._entries[0][1]["main_info"]["user_score"] == 3


def test_english_story_save_reopens_in_russian_collection_without_mislabeling_or_merging_tv(
    qtbot, tmp_path, monkeypatch,
):
    from contextlib import closing
    import json
    import sqlite3

    from candidates.story_search import StoryDocument, StoryHit
    from desktop.settings.app_settings import APP_DATA_LANGUAGE_ENV, APP_INTERFACE_LANGUAGE_ENV
    from desktop.story.view import StorySearchView
    from storage.sqlite.connection import get_db_path

    monkeypatch.setenv(APP_INTERFACE_LANGUAGE_ENV, "ru")
    monkeypatch.setenv(APP_DATA_LANGUAGE_ENV, "ru")
    db = get_db_path()
    assert db.resolve().is_relative_to(tmp_path.resolve())
    identifier = 12994
    rows = (
        ("movie", "en", "A Lantern at Dawn", "An engineer saves a ferry before dawn."),
        ("tv", "ru", "Огни на берегу", "Капитан ищет пропавшую команду."),
    )
    expected = {}
    for kind, locale, title, overview in rows:
        key = f"tmdb:{kind}:{identifier}"
        localized = {locale: {"title": title, "overview": overview}}
        expected[key] = localized
        candidate = {
            "title": title, "overview": overview, "media_type": kind, "tmdb_id": identifier,
            "year": 2024, "source": "TMDb", "source_provider": "tmdb", "localized": localized,
        }
        # The existing online protocol still refuses English. Inject the
        # future typed record at the shared card renderer, not the HTTP parser;
        # actual Save clicks, persistence and Collection are unchanged.
        story = StorySearchView()
        qtbot.addWidget(story.widget)
        doc = StoryDocument(key, title, overview, kind, "fixture", year=2024)
        story._render_cards([StoryHit(doc, 0.0, overview)], {key: candidate}, online=True)
        story.widget.resize(1200, 850)
        story.widget.show()
        save = story.widget.findChild(QPushButton, "storySaveAction")
        assert save is not None and save.isEnabled()
        click(qtbot, save)
        assert save.text() == "В коллекции" and not save.isEnabled()
        story.prepare_for_shutdown()
        story.widget.close()

    # Save's SQLite connections have closed. A new, read-only connection
    # verifies the actual persisted payloads before a fresh Collection widget.
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        saved = conn.execute("SELECT identity_key, candidate_json FROM candidate_actions WHERE action='watchlist'").fetchall()
    assert len(saved) == len(rows)
    assert {key: json.loads(raw)["candidate"]["localized"] for key, raw in saved} == expected

    collection = open_collection(qtbot)
    assert collection.legacy._data_language == "ru"
    assert set(collection.legacy._action_candidates_by_key) == {f"__candidate__{key}" for key in expected}
    assert len(cards(collection)) == len(rows)
    displayed = {
        (card.findChild(QLabel, "storyTitle").text(), card.findChild(QLabel, "storyEvidence").text())
        for card in cards(collection)
    }
    assert displayed == {(title, overview) for _, _, title, overview in rows}
    collection.prepare_for_shutdown()
    collection.widget.close()
