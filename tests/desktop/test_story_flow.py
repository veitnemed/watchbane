from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QMessageBox
from desktop.story.view import StorySearchView
from candidates.story_search import StorySearch, StoryDocument


def run_search(qtbot, view, query):
    view.query.setText(query)
    qtbot.mouseClick(view.search_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: view._worker is None, timeout=10000)


def test_empty_catalog_does_not_run_demo_or_start_background_work(qtbot, monkeypatch):
    from candidates import service
    view = StorySearchView()
    qtbot.addWidget(view.widget); view.widget.resize(1100, 850); view.widget.show()
    view.widget.activateWindow()
    qtbot.waitUntil(view.widget.isActiveWindow)
    monkeypatch.setattr(service, "local_story_catalog", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no search")))
    assert view.query.isEnabled() and not view.search_button.isEnabled()
    assert view.query.placeholderText() == "Для поиска нужен каталог"
    assert view.catalog_button.isVisible() and view.snapshot_button.isVisible()
    view.query.setFocus()
    view.query.setText("сериал про пристурника")
    qtbot.keyClick(view.query, Qt.Key.Key_Return)
    assert view._worker is None and view.cards_layout.count() == 1
    assert "Загрузите" in view.status.text()
    assert view.query.hasFocus() and view.query.text() == "сериал про пристурника"
    assert "TMDb" in view.status.text() and "файл каталога" in view.status.text()
    assert view.heading.isVisible() and view.examples.isEnabled()
    example = view.examples.findChildren(QPushButton)[0]
    qtbot.mouseClick(example, Qt.MouseButton.LeftButton)
    assert view.query.text() == example.text()
    assert view._worker is None and not view.search_button.isEnabled()
    assert view.cards_layout.count() == 1


def test_local_actions_use_existing_storage(qtbot, monkeypatch):
    from candidates import service
    from candidates import story_service
    from candidates.title_state_service import get_title_state, remove_from_watchlist
    candidate = {"title":"Local fictional", "year":2025, "media_type":"tv", "tmdb_id":99117,
                 "overview":"Преступник планирует ограбление.","source":"synthetic"}
    monkeypatch.setattr(story_service,"get_pool_view",lambda:[candidate])
    view = StorySearchView(); qtbot.addWidget(view.widget); view.widget.resize(1100, 850); view.widget.show()
    run_search(qtbot, view, "преступник")
    card = view.cards_layout.itemAt(0).widget()
    more = next(b for b in card.findChildren(QPushButton) if b.text() == "Полный сюжет")
    qtbot.mouseClick(more, Qt.MouseButton.LeftButton)
    assert more.text() == "Свернуть сюжет" and more.isChecked()
    assert not card.findChild(QLabel, "storyEvidence").isVisible()
    save = next(b for b in card.findChildren(QPushButton) if b.text() == "Сохранить")
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    assert get_title_state(candidate) == "watchlist"
    assert view.cards_layout.itemAt(0).widget() is card
    assert not save.isEnabled() and save.text() == "В коллекции"
    assert more.isChecked()
    run_search(qtbot, view, "преступник")
    saved = next(b for b in view.cards.findChildren(QPushButton) if b.text() == "В коллекции")
    assert not saved.isEnabled()
    remove_from_watchlist(candidate)
    run_search(qtbot, view, "преступник")
    assert any(button.text() == "Сохранить" and button.isEnabled()
               for button in view.cards.findChildren(QPushButton))
    monkeypatch.setattr(QMessageBox,"question",lambda *a: QMessageBox.StandardButton.Yes)
    watched = next(b for b in view.cards.findChildren(QPushButton) if b.text() == "Смотрел")
    qtbot.mouseClick(watched, Qt.MouseButton.LeftButton)
    assert get_title_state(candidate) == "watched"
    run_search(qtbot, view, "преступник")
    assert view.cards_layout.count() == 1


def test_home_does_not_schedule_token_gate(qtbot, monkeypatch):
    from desktop.shell.main_window import WatchedMoviesWindow
    window = WatchedMoviesWindow(initial_size=(1100,800))
    qtbot.addWidget(window)
    window.schedule_tmdb_startup_gate(0)
    assert window._main_tabs.currentWidget() is window._tab_registry._specs["story"].view.widget
    assert not window._tmdb_gate_timer.isActive()
    assert window._onboarding_view is None
    assert {"watched","candidates","filters","settings"} <= set(window._tab_registry._specs)
    window.shutdown_background_workers()


def test_worker_failure_is_recoverable_and_enter_starts_search(qtbot, monkeypatch):
    from candidates import service, story_service
    candidate = {"title": "Fixture", "tmdb_id": 513, "media_type": "movie", "overview": "Туристы летят в космос."}
    monkeypatch.setattr(story_service, "get_pool_view", lambda: [candidate])
    local = service.local_story_catalog
    monkeypatch.setattr(service, "local_story_catalog", lambda *a, **k: (_ for _ in ()).throw(OSError("test")))
    view=StorySearchView(); qtbot.addWidget(view.widget); view.widget.resize(1100, 850); view.widget.show()
    view.query.setText("космос")
    qtbot.keyClick(view.query, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: view._worker is None)
    assert "Не удалось" in view.status.text()
    assert view.search_button.isEnabled()
    monkeypatch.setattr(service, "local_story_catalog", local)
    run_search(qtbot, view, "космос")
    assert view.cards_layout.count() == 2


def test_home_and_empty_query_do_not_request_network(qtbot, monkeypatch):
    import requests
    calls=[]
    def deny(*args,**kwargs):
        calls.append(args); raise AssertionError("offline home attempted network")
    monkeypatch.setattr(requests.Session,"request",deny)
    from desktop.shell.main_window import WatchedMoviesWindow
    window=WatchedMoviesWindow(initial_size=(1100,800));qtbot.addWidget(window);window.show()
    window.schedule_tmdb_startup_gate(0)
    run_search(qtbot,window._tab_registry._specs["story"].view,"преступник")
    qtbot.wait(300)
    assert not calls
    window.shutdown_background_workers()


def test_busy_search_keeps_input_and_runs_latest_query(qtbot, monkeypatch):
    from threading import Event
    from candidates import service
    gate = Event()
    calls = []
    engine = StorySearch([StoryDocument('one','A','Врач лечит пациентов.','tv','authored',demo=False)])
    real_search = engine.search
    def slow(query, **kwargs):
        calls.append(query)
        gate.wait(3)
        return real_search(query, **kwargs)
    engine.search = slow
    monkeypatch.setattr(service, "story_catalog_snapshot", lambda: ((engine.documents[0],), {}))
    monkeypatch.setattr(service, "local_story_catalog", lambda *a, **k: (engine, {}))
    view = StorySearchView()
    qtbot.addWidget(view.widget); view.widget.resize(1100,850); view.widget.show()
    view.query.setText('первый'); view.search()
    qtbot.waitUntil(lambda: bool(calls))
    assert view.query.isEnabled()
    view.query.setText('второй'); view.search()
    view.query.setText('врач'); view.search()
    gate.set()
    qtbot.waitUntil(lambda: view._worker is None,timeout=5000)
    assert calls == ['первый','врач']
    view.prepare_for_shutdown(); view.query.setText('после закрытия'); view.search()
    assert view._worker is None


def test_save_failure_leaves_result_and_retry_available(qtbot, monkeypatch):
    from candidates import service, story_service
    candidate = {"title": "Retry fixture", "tmdb_id": 90128, "media_type": "movie",
                 "overview": "Врач лечит людей в больнице.", "source": "synthetic"}
    monkeypatch.setattr(story_service, "get_pool_view", lambda: [candidate])
    real_save = service.add_candidate_to_watchlist
    monkeypatch.setattr(service, "add_candidate_to_watchlist", lambda _: {"ok": False})
    view = StorySearchView()
    qtbot.addWidget(view.widget)
    view.widget.show()
    run_search(qtbot, view, "врач")
    card = view.cards_layout.itemAt(0).widget()
    save = next(b for b in card.findChildren(QPushButton) if b.text() == "Сохранить")
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    assert save.isEnabled() and save.text() == "Сохранить"
    assert view.cards_layout.itemAt(0).widget() is card
    assert "Не удалось" in view.status.text()
    monkeypatch.setattr(service, "add_candidate_to_watchlist", real_save)
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    assert not save.isEnabled()


def test_profile_story_search_and_save_keep_two_persisted_tmdb_homonyms(qtbot, monkeypatch):
    from contextlib import closing
    from candidates import service
    from candidates.title_state_service import get_title_state, mark_watched
    from storage.sqlite.candidate_pool_repository import load_candidate_pool_dict
    from storage.sqlite.candidate_write import insert_candidate_record
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations
    from storage.sqlite.session import utc_now

    for name in ("WATCHBANE_STORY_SEED_CATALOG", "WATCHBANE_STORY_MODEL_DIR"):
        monkeypatch.delenv(name, raising=False)
    first = {"title": "Тёзки", "year": 2020, "media_type": "movie", "tmdb_id": 101,
             "overview": "Преступник скрывается от полиции в горах."}
    second = {**first, "tmdb_id": 202, "overview": "Преступник ограбил банк и бежал через лес."}
    with closing(connect()) as conn:
        apply_migrations(conn)
        with conn:
            insert_candidate_record(conn, pool_key="legacy:first", candidate=first, timestamp=utc_now())
            insert_candidate_record(conn, pool_key="opaque:second", candidate=second, timestamp=utc_now())
    before = load_candidate_pool_dict()

    docs, records = service.story_catalog_snapshot()
    assert {doc.key for doc in docs} == {"tmdb:movie:101", "tmdb:movie:202"}
    assert {records[doc.key]["tmdb_id"] for doc in docs} == {101, 202}
    assert load_candidate_pool_dict() == before

    view = StorySearchView()
    qtbot.addWidget(view.widget)
    view.widget.resize(1100, 850)
    view.widget.show()
    run_search(qtbot, view, "преступник")
    assert view.cards_layout.count() == 3
    buttons = []
    for i in range(2):
        card = view.cards_layout.itemAt(i).widget()
        buttons.append(card.findChild(QPushButton, "storySaveAction"))
    assert all(b.isEnabled() for b in buttons)
    qtbot.mouseClick(buttons[0], Qt.MouseButton.LeftButton)
    assert {get_title_state(first), get_title_state(second)} == {"available", "watchlist"}
    qtbot.mouseClick(buttons[1], Qt.MouseButton.LeftButton)
    assert get_title_state(first) == get_title_state(second) == "watchlist"
    assert load_candidate_pool_dict() == before

    mark_watched(first)
    _, remaining = service.story_catalog_snapshot()
    assert set(remaining) == {"tmdb:movie:202"}
    assert get_title_state(second) == "watchlist"



def test_story_watched_legacy_without_id_does_not_hide_known_homonyms():
    from candidates import service
    from candidates.title_state_service import mark_watched

    legacy = {"title": "Одно имя", "year": 2001, "media_type": "movie"}
    first = {**legacy, "tmdb_id": 301, "overview": "Полицейский расследует кражу."}
    second = {**legacy, "tmdb_id": 302, "overview": "Преступник скрывается от полиции."}
    mark_watched(legacy)
    assert not service.story_catalog_snapshot([first])[0]
    docs, _ = service.story_catalog_snapshot([first, second])
    assert {doc.key for doc in docs} == {"tmdb:movie:301", "tmdb:movie:302"}
