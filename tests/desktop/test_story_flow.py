from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QMessageBox
from desktop.story.view import StorySearchView
from candidates.story_search import StorySearch, StoryDocument


def run_search(qtbot, view, query):
    view.query.setText(query)
    qtbot.mouseClick(view.search_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: view._worker is None, timeout=10000)


def test_demo_search_hide_empty_and_negation(qtbot, monkeypatch):
    from candidates import service
    monkeypatch.setattr(service, "hide_candidate", lambda _: (_ for _ in ()).throw(AssertionError("demo must not write")))
    view = StorySearchView()
    qtbot.addWidget(view.widget); view.widget.resize(1100, 850); view.widget.show()
    run_search(qtbot, view, "сериал про пристурника")
    assert view.cards_layout.count() == 6
    titles_before = [w.text() for w in view.cards.findChildren(QLabel, "storyTitle")]
    hide = view.cards.findChildren(QPushButton)[0]
    qtbot.mouseClick(hide, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: view.cards_layout.count() == 5)
    assert view.cards_layout.count() == 5  # no surprise refill
    run_search(qtbot, view, "сериал про пристурника")
    assert titles_before[0] not in [w.text() for w in view.cards.findChildren(QLabel, "storyTitle")]
    run_search(qtbot, view, "без преступников")
    assert view.cards_layout.count() == 1
    assert "Отрицания" in view.status.text()
    run_search(qtbot, view, "орхидея")
    assert "Совпадений нет" in view.status.text()


def test_local_actions_use_existing_storage(qtbot, monkeypatch):
    from candidates import service
    from candidates import story_service
    from candidates.title_state_service import get_title_state, remove_from_watchlist
    candidate = {"title":"Local fictional", "year":2025, "media_type":"tv", "tmdb_id":99117,
                 "overview":"Преступник планирует ограбление.","source":"synthetic"}
    monkeypatch.setattr(story_service,"get_pool_view",lambda:[candidate])
    view = StorySearchView(); qtbot.addWidget(view.widget); view.widget.resize(1100, 850); view.widget.show()
    view.mode.setCurrentIndex(1)
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
    from candidates import service
    monkeypatch.setattr(service,"local_story_catalog",lambda: (_ for _ in ()).throw(OSError("test")))
    view=StorySearchView(); qtbot.addWidget(view.widget); view.widget.resize(1100, 850); view.widget.show()
    view.mode.setCurrentIndex(1); view.query.setText("преступник")
    qtbot.keyClick(view.query, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: view._worker is None)
    assert "Не удалось" in view.status.text()
    assert view.search_button.isEnabled() and view.mode.isEnabled()
    view.mode.setCurrentIndex(0)
    run_search(qtbot,view,"космос")
    assert view.cards_layout.count()>1


def test_home_and_demo_do_not_request_network(qtbot, monkeypatch):
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
    engine = StorySearch([StoryDocument('one','A','Врач лечит пациентов.','tv','authored',demo=True)])
    real_search = engine.search
    def slow(query, **kwargs):
        calls.append(query)
        gate.wait(3)
        return real_search(query, **kwargs)
    engine.search = slow
    monkeypatch.setattr(service,'create_story_search',lambda *a,**k:engine)
    view = StorySearchView(); view.mode.setCurrentIndex(0)
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
    view.mode.setCurrentIndex(1)
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
