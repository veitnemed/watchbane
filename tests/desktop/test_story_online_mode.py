from threading import Event, get_ident

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from candidates.title_state_service import STATE_WATCHLIST, get_title_state
from desktop.story import online_client, view as story


LEFT = Qt.MouseButton.LeftButton


def make_view(qtbot):
    view = story.StorySearchView()
    qtbot.addWidget(view.widget)
    view.widget.resize(1100, 850)
    view.widget.show()
    return view


@pytest.mark.parametrize("configuration", [None, "0", "65536", "localhost", "https://remote.invalid"])
def test_no_experimental_control_or_transport_by_default(qtbot, monkeypatch, configuration):
    if configuration is None:
        monkeypatch.delenv(story._ONLINE_PORT_ENV, raising=False)
    else:
        monkeypatch.setenv(story._ONLINE_PORT_ENV, configuration)
    view = make_view(qtbot)
    monkeypatch.setattr(online_client, "search_online", lambda *_a, **_kw: pytest.fail("unexpected transport"))
    view.query.setText("черновик")
    view.on_tab_activated()
    qtbot.keyClick(view.query, Qt.Key.Key_Return)
    assert view.online_button.isHidden() and view._online_worker is None
    assert "Загрузите описания из TMDb или откройте файл каталога." in view.status.text()
    assert "тестовом сервере" not in view.status.text()


def test_explicit_cancel_default_and_requery_consent(qtbot, monkeypatch):
    monkeypatch.setenv(story._ONLINE_PORT_ENV, "8765")
    calls = []
    monkeypatch.setattr(online_client, "search_online", lambda *args, **kwargs: calls.append((args, kwargs)) or ())
    prompts = []

    def reject(dialog):
        prompts.append((dialog.text(), dialog.defaultButton().text()))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "exec", reject)
    view = make_view(qtbot)
    view.query.setText("не отправлять без действия")
    view.on_tab_activated()
    qtbot.keyClick(view.query, Qt.Key.Key_Return)
    assert not calls and not prompts
    qtbot.mouseClick(view.online_button, LEFT)
    assert len(prompts) == 1 and not calls
    assert "127.0.0.1:8765" in prompts[0][0] and prompts[0][1] == "Не отправлять"

    def edit_during_modal(*args):
        view.query.setText("другой текст")
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "exec", edit_during_modal)
    qtbot.mouseClick(view.online_button, LEFT)
    assert not calls and view.query.text() == "другой текст"


def test_accepted_result_runs_on_worker_and_saves_typed_movie_and_tv(qtbot, monkeypatch):
    monkeypatch.setenv(story._ONLINE_PORT_ENV, "32123")
    monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
    main_thread, received = get_ident(), []

    def request(query, *, consent, port, cancelled):
        received.append((query, consent, port, get_ident(), cancelled.is_set()))
        return tuple(online_client.OnlineStoryResult(
            f"tmdb:{media}:349884", media, f"Тёзка {media}", 2005, "Возвращается домой.", "Возвращается"
        ) for media in ("movie", "tv"))

    monkeypatch.setattr(online_client, "search_online", request)
    view = make_view(qtbot)
    monkeypatch.setattr(view.posters, "bind", lambda *_: pytest.fail("online result must not fetch a poster"))
    view.query.setText(" возвращение ")
    qtbot.mouseClick(view.online_button, LEFT)
    qtbot.waitUntil(lambda: view._online_worker is None)
    assert received == [("возвращение", True, 32123, received[0][3], False)]
    assert received[0][3] != main_thread
    assert "тестового сервера: 2" in view.status.text()
    assert any("Тестовый сервер" in label.text() for label in view.cards.findChildren(QLabel))
    buttons = view.cards.findChildren(QPushButton, "storySaveAction")
    assert len(buttons) == 2
    for button in buttons:
        qtbot.mouseClick(button, LEFT)
    assert not any(button.isEnabled() for button in buttons)
    for media in ("movie", "tv"):
        assert get_title_state({"tmdb_id": 349884, "media_type": media, "title": f"Тёзка {media}"}) == STATE_WATCHLIST


@pytest.mark.parametrize("how", ["edit", "button", "shutdown"])
def test_in_flight_cancel_suppresses_late_hits_without_second_send(qtbot, monkeypatch, how):
    monkeypatch.setenv(story._ONLINE_PORT_ENV, "8765")
    monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
    entered = Event()
    calls = []

    def breach(query, *, consent, port, cancelled):
        calls.append(query)
        entered.set()
        if cancelled.wait(2):
            return (online_client.OnlineStoryResult("tmdb:tv:1", "tv", "Устаревший", None, "сюжет", ""),)
        return ()

    monkeypatch.setattr(online_client, "search_online", breach)
    view = make_view(qtbot)
    view.query.setText("запрос")
    qtbot.mouseClick(view.online_button, LEFT)
    qtbot.waitUntil(entered.is_set)
    assert view.online_cancel.isVisible() and not view.online_button.isEnabled()
    if how == "edit":
        view.query.setText("новый запрос")
    elif how == "button":
        qtbot.mouseClick(view.online_cancel, LEFT)
    else:
        view.prepare_for_shutdown()
    qtbot.waitUntil(lambda: view._online_worker is None)
    assert calls == ["запрос"] and view.cards_layout.count() == 1
    assert view.online_cancel.isHidden()
    if how != "shutdown":
        assert "отменён" in view.status.text() and view.online_button.isEnabled()


def test_failed_server_does_not_fall_back_on_tab_focus(qtbot, monkeypatch):
    monkeypatch.setenv(story._ONLINE_PORT_ENV, "8765")
    monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)

    def offline(*_args, **_kwargs):
        raise online_client.OnlineStoryError("private infrastructure response")

    monkeypatch.setattr(online_client, "search_online", offline)
    view = make_view(qtbot)
    view.query.setText("текст остаётся")
    qtbot.mouseClick(view.online_button, LEFT)
    qtbot.waitUntil(lambda: view._online_worker is None)
    assert "не ответил" in view.status.text() and "private" not in view.status.text()
    monkeypatch.setattr(view, "search", lambda: pytest.fail("hidden local fallback"))
    view.on_tab_activated()
    assert view.query.text() == "текст остаётся" and view.online_button.isEnabled()


def test_qt_uses_real_loopback_http_and_keeps_fixed_payload(qtbot, monkeypatch):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json
    from threading import Thread

    sent = []
    body = json.dumps({"source": "tmdb", "results": [{
        "id": "tmdb:tv:152229", "media_type": "tv", "title": "Контроль",
        "year": 2022, "overview": "Следователь находит древний артефакт.",
        "evidence": "древний артефакт", "language": "ru-RU",
    }]}).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            sent.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    try:
        server = HTTPServer(("127.0.0.1", 0), Handler)
    except PermissionError:
        pytest.skip("Execution sandbox does not permit opening a loopback socket")
    with server:
        worker = Thread(target=server.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
        worker.start()
        try:
            monkeypatch.setenv(story._ONLINE_PORT_ENV, str(server.server_port))
            monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
            view = make_view(qtbot)
            view.query.setText("сюжет про находку")
            qtbot.mouseClick(view.online_button, LEFT)
            qtbot.waitUntil(lambda: view._online_worker is None)
            assert sent == [("/v1/search", {"query": "сюжет про находку", "limit": 5})]
            assert view.cards.findChild(QLabel, "storyTitle").text() == "Контроль"
            button = view.cards.findChild(QPushButton, "storySaveAction")
            qtbot.mouseClick(button, LEFT)
            assert get_title_state({"tmdb_id": 152229, "media_type": "tv", "title": "Контроль"}) == STATE_WATCHLIST
        finally:
            server.shutdown()
            worker.join()


def test_online_cards_scroll_without_squeezing_button_labels(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QScrollArea
    from desktop.theme.scaling import set_ui_scale

    monkeypatch.setenv(story._ONLINE_PORT_ENV, "8765")
    monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(online_client, "search_online", lambda *_a, **_kw: tuple(
        online_client.OnlineStoryResult(f"tmdb:movie:{i}", "movie", f"Фильм {i}", None,
                                        "Длинный сюжет " * 20, "Длинный фрагмент " * 12)
        for i in range(1, 6)
    ))
    set_ui_scale(1.25)
    try:
        view = make_view(qtbot)
        view.widget.resize(1280, 900)
        view.query.setText("запрос")
        qtbot.mouseClick(view.online_button, LEFT)
        qtbot.waitUntil(lambda: view._online_worker is None)
        scroll = view.widget.findChild(QScrollArea)
        qtbot.waitUntil(lambda: scroll.verticalScrollBar().maximum() > 0)
        buttons = view.cards.findChildren(QPushButton, "storySaveAction")
        assert len(buttons) == 5
        assert all(button.height() >= button.fontMetrics().height() for button in buttons)
        cards = [view.cards_layout.itemAt(i).widget() for i in range(5)]
        assert all(upper.geometry().bottom() < lower.geometry().top() for upper, lower in zip(cards, cards[1:]))
    finally:
        set_ui_scale(1.0)


@pytest.mark.parametrize("dismiss_key", [Qt.Key.Key_Return, Qt.Key.Key_Escape])
def test_empty_local_catalog_copy_and_real_default_deny(qtbot, monkeypatch, dismiss_key):
    monkeypatch.setenv(story._ONLINE_PORT_ENV, "8765")
    sent, inspected = [], []
    monkeypatch.setattr(online_client, "search_online", lambda *_a, **_kw: sent.append(True) or ())
    view = make_view(qtbot)
    assert "не нужны локальные каталог и модель" in view.status.text()
    assert "Для локального поиска" in view.status.text()
    view.query.setText("черновик")
    qtbot.keyClick(view.query, Qt.Key.Key_Return)
    assert view.online_button.isEnabled() and not view.search_button.isEnabled()
    assert not sent

    def dismiss():
        modal = QApplication.activeModalWidget()
        inspected.append((modal.button(QMessageBox.StandardButton.Yes).text(),
                          modal.defaultButton().text(), modal.escapeButton().text()))
        qtbot.keyClick(modal, dismiss_key)

    QTimer.singleShot(0, dismiss)
    qtbot.mouseClick(view.online_button, LEFT)
    assert inspected == [("Отправить запрос", "Не отправлять", "Не отправлять")]
    assert not sent and view.query.text() == "черновик" and view._online_worker is None


@pytest.mark.parametrize("real_http", [False, True], ids=["worker-only", "loopback-http"])
def test_busy_is_editable_and_retries_only_with_a_second_consent(qtbot, monkeypatch, real_http):
    from contextlib import ExitStack
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread

    requests = []
    prompts = []
    decisions = iter((QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No,
                      QMessageBox.StandardButton.Yes))

    def confirm(_dialog):
        prompts.append("shown")
        return next(decisions)

    monkeypatch.delenv(story._ONLINE_OUTCOME_ENV, raising=False)
    monkeypatch.setattr(QMessageBox, "exec", confirm)

    with ExitStack() as stack:
        if real_http:
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_args):
                    pass

                def do_POST(self):
                    requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"])))["query"])
                    busy = len(requests) == 1
                    data = b'{"detail":"search_busy"}' if busy else json.dumps({"source": "tmdb", "results": [{
                        "id": "tmdb:tv:42", "media_type": "tv", "title": "Fixture", "year": 2020,
                        "overview": "A test plot", "evidence": "", "language": "ru-RU",
                    }]}).encode()
                    self.send_response(503 if busy else 200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

            try:
                server = stack.enter_context(HTTPServer(("127.0.0.1", 0), Handler))
            except PermissionError:
                pytest.skip("Loopback bind not permitted")
            thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
            thread.start()
            stack.callback(thread.join, 2)
            stack.callback(server.shutdown)
            port = server.server_port
        else:
            def request(query, **_):
                requests.append(query)
                if len(requests) == 1:
                    raise online_client.OnlineStoryBusy("fixed")
                return (online_client.OnlineStoryResult("tmdb:tv:42", "tv", "Fixture", 2020, "A test plot", ""),)

            monkeypatch.setattr(online_client, "search_online", request)
            port = 8765

        monkeypatch.setenv(story._ONLINE_PORT_ENV, str(port))
        view = make_view(qtbot)
        view.query.setText("первый сюжет")
        qtbot.mouseClick(view.online_button, LEFT)
        qtbot.waitUntil(lambda: view._online_worker is None)
        assert "занят другим запросом" in view.status.text()
        assert view.query.text() == "первый сюжет" and view.online_button.isEnabled()
        assert view.query.isEnabled() and view.cards_layout.count() == 1
        view.on_tab_activated()
        view.query.setText("отредактированный сюжет")
        qtbot.wait(30)
        assert requests == ["первый сюжет"] and len(prompts) == 1
        qtbot.mouseClick(view.online_button, LEFT)  # Explicit decline: still no POST.
        assert requests == ["первый сюжет"] and len(prompts) == 2
        qtbot.mouseClick(view.online_button, LEFT)
        qtbot.waitUntil(lambda: view._online_worker is None)
        assert requests == ["первый сюжет", "отредактированный сюжет"] and len(prompts) == 3
        assert "тестового сервера: 1" in view.status.text()


def test_late_busy_cannot_overwrite_cancel_on_edit(qtbot, monkeypatch):
    monkeypatch.setenv(story._ONLINE_PORT_ENV, "8765")
    monkeypatch.delenv(story._ONLINE_OUTCOME_ENV, raising=False)
    monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
    entered = Event()

    def request(query, *, cancelled, **_):
        entered.set()
        assert cancelled.wait(2)
        raise online_client.OnlineStoryBusy("late")
    monkeypatch.setattr(online_client, "search_online", request)
    view = make_view(qtbot)
    view.query.setText("исходный запрос")
    qtbot.mouseClick(view.online_button, LEFT)
    qtbot.waitUntil(entered.is_set)
    view.query.setText("новый запрос")
    qtbot.waitUntil(lambda: view._online_worker is None)
    assert "отменён" in view.status.text() and "занят" not in view.status.text()
    assert view.query.text() == "новый запрос"
