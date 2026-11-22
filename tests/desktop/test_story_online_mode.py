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
    monkeypatch.delenv(story._ONLINE_ARTWORK_ENV, raising=False)
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
    from desktop.shared import story_posters
    monkeypatch.setattr(story_posters, "cached_provider_picture",
                        lambda *_: pytest.fail("default online results must not read poster cache"))
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
@pytest.mark.parametrize("initial_reply", ["busy", "rate-limited", "malformed-rate-limit"])
def test_failed_or_budgeted_request_retries_only_with_fresh_consent(qtbot, monkeypatch, real_http, initial_reply):
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
                    first = len(requests) == 1
                    code = (503 if initial_reply == "busy" else 429) if first else 200
                    if code == 503:
                        data = b'{"detail":"search_busy"}'
                    elif code == 429:
                        data = b'{"detail":"search_rate_limited"}'
                    else:
                        data = json.dumps({"source": "tmdb", "results": [{
                            "id": "tmdb:tv:42", "media_type": "tv", "title": "Fixture", "year": 2020,
                            "overview": "A test plot", "evidence": "", "language": "ru-RU",
                        }]}).encode()
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-store")
                    if code == 429:
                        self.send_header("Retry-After", "7" if initial_reply == "rate-limited" else "61")
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
                    if initial_reply == "busy":
                        raise online_client.OnlineStoryBusy("fixed")
                    if initial_reply == "rate-limited":
                        raise online_client.OnlineStoryRateLimited(7)
                    raise online_client.OnlineStoryError("fixed")
                return (online_client.OnlineStoryResult("tmdb:tv:42", "tv", "Fixture", 2020, "A test plot", ""),)

            monkeypatch.setattr(online_client, "search_online", request)
            port = 8765

        monkeypatch.setenv(story._ONLINE_PORT_ENV, str(port))
        view = make_view(qtbot)
        view.query.setText("первый сюжет")
        qtbot.mouseClick(view.online_button, LEFT)
        qtbot.waitUntil(lambda: view._online_worker is None)
        notice = {
            "busy": "занят другим запросом",
            "rate-limited": "Слишком частые запросы. Повторите поиск через 7 с.",
            "malformed-rate-limit": "не ответил или вернул ошибку",
        }[initial_reply]
        assert notice in view.status.text()
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


@pytest.mark.parametrize("error", [online_client.OnlineStoryBusy("late"), online_client.OnlineStoryRateLimited(7)])
def test_late_busy_or_cooldown_cannot_overwrite_cancel_on_edit(qtbot, monkeypatch, error):
    monkeypatch.setenv(story._ONLINE_PORT_ENV, "8765")
    monkeypatch.delenv(story._ONLINE_OUTCOME_ENV, raising=False)
    monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
    entered = Event()

    def request(query, *, cancelled, **_):
        entered.set()
        assert cancelled.wait(2)
        raise error
    monkeypatch.setattr(online_client, "search_online", request)
    view = make_view(qtbot)
    view.query.setText("исходный запрос")
    qtbot.mouseClick(view.online_button, LEFT)
    qtbot.waitUntil(entered.is_set)
    view.query.setText("новый запрос")
    qtbot.waitUntil(lambda: view._online_worker is None)
    assert "отменён" in view.status.text() and "занят" not in view.status.text()
    assert "Слишком частые" not in view.status.text()
    assert view.query.text() == "новый запрос"


@pytest.mark.parametrize("real_cached_poster", [False, True])
def test_loopback_artwork_reads_only_existing_exact_typed_poster(qtbot, monkeypatch, tmp_path, real_cached_poster):
    from hashlib import sha256
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json
    import os
    from pathlib import Path
    from threading import Thread

    from PyQt6.QtGui import QColor, QImage
    from desktop.shared import story_posters
    from posters import download_images

    cache = tmp_path / "preview"
    cache.mkdir()
    monkeypatch.setattr(download_images, "PREVIEW_POSTER_DIR", cache)
    monkeypatch.setenv(story._ONLINE_ARTWORK_ENV, "1")
    monkeypatch.delenv(story._ONLINE_OUTCOME_ENV, raising=False)
    path = "/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg" if real_cached_poster else "/generated-qa.jpg"
    destination = download_images.preview_poster_path_for_url("https://image.tmdb.org/t/p/w342" + path)
    if real_cached_poster:
        source = os.environ.get("WATCHBANE_QA_REAL_CACHED_POSTER")
        if not source:
            pytest.skip("Pinned local QA-only Interstellar cache entry not supplied")
        raw_cache = Path(source).read_bytes()
        assert sha256(raw_cache).hexdigest() == "fc6fd15def01f9f728c92f9e8ee87f404426819b4e51d6dc53c186225e847382"
        destination.write_bytes(raw_cache)
    else:
        image = QImage(2, 3, QImage.Format.Format_RGB32)
        image.fill(QColor("#805aad"))
        assert image.save(str(destination), "PNG")
        raw_cache = destination.read_bytes()

    received, image_gets = [], []
    rows = [{
        "id": f"tmdb:{kind}:157336", "media_type": kind, "title": title,
        "year": 2014, "overview": "Астронавты ищут новый дом.", "evidence": "ищут новый дом", "language": "ru-RU",
    } for kind, title in (("movie", "Интерстеллар"), ("tv", "Отдельная фикстура сериала"))]
    body = json.dumps({"source": "tmdb", "results": rows, "artwork": {"tmdb:movie:157336": path}}).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                             self.headers.get("Watchbane-Search-Artwork")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Watchbane-Search-Artwork", "1")
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
            view = make_view(qtbot)

            def blocked(*args):
                image_gets.append(1)
                raise AssertionError("Online artwork must never use the download queue")

            monkeypatch.setattr(view.posters, "bind", blocked)
            monkeypatch.setattr(view.posters.controller._manager, "get", blocked)
            open_attempts = []
            real_read = story_posters.cached_provider_picture

            def cache_read(*args):
                open_attempts.append(args[0])
                return real_read(*args)

            monkeypatch.setattr(story_posters, "cached_provider_picture", cache_read)
            view.query.setText("сюжет про находку")
            monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.No)
            qtbot.mouseClick(view.online_button, LEFT)
            assert not open_attempts and not received

            monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
            qtbot.mouseClick(view.online_button, LEFT)
            qtbot.waitUntil(lambda: view._online_worker is None)
            posters = view.cards.findChildren(QLabel, "storyPoster")
            assert len(posters) == 2
            assert posters[0].accessibleName() == "Постер: Интерстеллар" and not posters[0].pixmap().isNull()
            assert posters[1].accessibleName() == "Постер недоступен" and posters[1].pixmap().isNull()
            assert received == [("/v1/search", {"query": "сюжет про находку", "limit": 5}, "1")]
            assert open_attempts == [path] and not image_gets
            assert destination.read_bytes() == raw_cache and list(cache.iterdir()) == [destination]
            assert all(not any(name in record for name in ("poster_path", "poster_url"))
                       for record in view._records.values())
            for button in view.cards.findChildren(QPushButton, "storySaveAction"):
                qtbot.mouseClick(button, LEFT)
            for media in ("movie", "tv"):
                assert get_title_state({"tmdb_id": 157336, "media_type": media}) == STATE_WATCHLIST
            assert not image_gets and destination.read_bytes() == raw_cache
        finally:
            server.shutdown()
            worker.join(2)


def test_cache_only_artwork_rejects_bad_paths_corrupt_oversized_and_symlink(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QImage
    from desktop.shared.story_posters import cached_provider_picture
    from posters import download_images

    monkeypatch.setattr(download_images, "PREVIEW_POSTER_DIR", tmp_path)
    canonical = "https://image.tmdb.org/t/p/w342"
    path, size = "/fixture.jpg", QSize(68, 94)
    cache = download_images.preview_poster_path_for_url(canonical + path)
    assert cached_provider_picture("https://image.tmdb.org" + path, size) is None
    assert cached_provider_picture("/../fixture.jpg", size) is None
    assert cached_provider_picture(path, size) is None

    broken = b"not an image"
    cache.write_bytes(broken)
    assert cached_provider_picture(path, size) is None and cache.read_bytes() == broken
    with cache.open("wb") as overflow:
        overflow.truncate(1024 * 1024 + 1)
    assert cached_provider_picture(path, size) is None
    cache.unlink()
    other = tmp_path / "other.png"
    assert QImage(2, 3, QImage.Format.Format_RGB32).save(str(other), "PNG")
    try:
        cache.symlink_to(other)
    except OSError:
        pytest.skip("Creating symlinks is unavailable on this test host")
    assert cached_provider_picture(path, size) is None and cache.is_symlink() and other.is_file()


def test_cache_only_artwork_rechecks_byte_limit_on_open_descriptor(qtbot, monkeypatch, tmp_path):
    import os

    from PyQt6.QtCore import QSize
    from desktop.shared import story_posters
    from posters import download_images

    monkeypatch.setattr(download_images, "PREVIEW_POSTER_DIR", tmp_path)
    path = "/fixture.jpg"
    cache = download_images.preview_poster_path_for_url("https://image.tmdb.org/t/p/w342" + path)
    cache.write_bytes(b"sized before open")
    positions = []

    def grow_after_open(name, flags):
        assert name == cache
        fd = original_open(name, flags)
        with cache.open("r+b") as file:
            file.truncate(1024 * 1024 + 1)
        return fd

    class ReadSpy:
        def __init__(self, fd, mode):
            self.stream = original_fdopen(fd, mode)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def fileno(self):
            return self.stream.fileno()

        def read(self, *args):
            positions.append(self.stream.tell())
            return self.stream.read(*args)

    original_open, original_fdopen = os.open, os.fdopen
    with monkeypatch.context() as patch:
        patch.setattr(story_posters.os, "open", grow_after_open)
        patch.setattr(story_posters.os, "fdopen", ReadSpy)
        assert story_posters.cached_provider_picture(path, QSize(68, 94)) is None
    assert cache.stat().st_size == 1024 * 1024 + 1
    assert not positions


@pytest.mark.parametrize("width,height", [(1025, 10), (10, 1537)])
def test_cache_only_artwork_rejects_over_dimension_compressed_source(qtbot, monkeypatch, tmp_path, width, height):
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QColor, QImage
    from desktop.shared.story_posters import cached_provider_picture
    from posters import download_images

    monkeypatch.setattr(download_images, "PREVIEW_POSTER_DIR", tmp_path)
    path = "/fixture.png"
    cache = download_images.preview_poster_path_for_url("https://image.tmdb.org/t/p/w342" + path)
    source = QImage(width, height, QImage.Format.Format_RGB32)
    source.fill(QColor("#805aad"))
    assert source.save(str(cache), "PNG")
    original = cache.read_bytes()
    assert len(original) < 1024 * 1024
    assert cached_provider_picture(path, QSize(68, 94)) is None
    assert cache.read_bytes() == original


def test_cache_only_artwork_drops_decoded_output_above_requested_size(qtbot, monkeypatch, tmp_path):
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QImage
    from desktop.shared import story_posters
    from posters import download_images

    monkeypatch.setattr(download_images, "PREVIEW_POSTER_DIR", tmp_path)
    path = "/fixture.png"
    cache = download_images.preview_poster_path_for_url("https://image.tmdb.org/t/p/w342" + path)
    cache.write_bytes(b"decoder stub")

    class IgnoresScale:
        def __init__(self, buffer):
            pass

        def size(self):
            return QSize(100, 200)

        def format(self):
            return b"png"

        def setScaledSize(self, _):
            pass

        def read(self):
            return QImage(100, 200, QImage.Format.Format_RGB32)

    monkeypatch.setattr(story_posters, "QImageReader", IgnoresScale)
    assert story_posters.cached_provider_picture(path, QSize(68, 94)) is None


def test_late_opt_in_artwork_is_never_read_after_cancellation(qtbot, monkeypatch):
    from desktop.shared import story_posters

    monkeypatch.setenv(story._ONLINE_PORT_ENV, "8765")
    monkeypatch.setenv(story._ONLINE_ARTWORK_ENV, "1")
    monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
    entered, reads = Event(), []

    def search(_query, *, consent, port, cancelled, with_artwork):
        assert consent and with_artwork
        entered.set()
        assert cancelled.wait(2)
        return (online_client.OnlineStoryResult("tmdb:tv:1", "tv", "Устаревший", None, "сюжет", "", "/late.jpg"),)

    monkeypatch.setattr(online_client, "search_online", search)
    monkeypatch.setattr(story_posters, "cached_provider_picture", lambda *_: reads.append(1))
    view = make_view(qtbot)
    view.query.setText("старый сюжет")
    qtbot.mouseClick(view.online_button, LEFT)
    qtbot.waitUntil(entered.is_set)
    view.query.setText("другой сюжет")
    qtbot.waitUntil(lambda: view._online_worker is None)
    assert not reads and view.cards_layout.count() == 1


def test_consented_loopback_shows_exact_index_size_only_on_negotiated_response(qtbot, monkeypatch):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json
    from threading import Thread

    sent = []
    replies = [
        (True, {"total": 3, "movies": 2, "tv": 1}),
        (False, {"total": 3, "movies": 2, "tv": 1}),
        (True, {"total": 30000, "movies": 20000, "tv": 10000}),
    ]

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            sent.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                         self.headers.get("Watchbane-Search-Index")))
            echo, index = replies.pop(0)
            row = {"source": "tmdb", "results": [], "index": index}
            body = json.dumps(row).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            if echo:
                self.send_header("Watchbane-Search-Index", "1")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    try:
        listener = HTTPServer(("127.0.0.1", 0), Handler)
    except PermissionError:
        pytest.skip("Execution sandbox does not permit opening a loopback socket")
    with listener:
        child = Thread(target=listener.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
        child.start()
        try:
            monkeypatch.setenv(story._ONLINE_PORT_ENV, str(listener.server_port))
            monkeypatch.setenv(story._ONLINE_INDEX_ENV, "1")
            monkeypatch.delenv(story._ONLINE_OUTCOME_ENV, raising=False)
            monkeypatch.delenv(story._ONLINE_ARTWORK_ENV, raising=False)
            ui = make_view(qtbot)
            ui.query.setText("описание фильма")
            monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.No)
            qtbot.mouseClick(ui.online_button, LEFT)
            assert not sent and "в индексе" not in ui.scope.text()
            monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
            for i in range(3):
                qtbot.mouseClick(ui.online_button, LEFT)
                qtbot.waitUntil(lambda: ui._online_worker is None)
                if i == 0:
                    assert ui.scope.text() == "Тестовый сервер · TMDb · Описаний в индексе: 3 (фильмы: 2, сериалы: 1)"
                    assert "не нашёл вариантов" in ui.status.text()
                else:
                    assert "в индексе" not in ui.scope.text() and "вернул ошибку" in ui.status.text()
                assert len(sent) == i + 1  # failure is never retried or downgraded
            assert all(x == ("/v1/search", {"query": "описание фильма", "limit": 5}, "1") for x in sent)
        finally:
            listener.shutdown()
            child.join(2)


def test_no_index_count_from_cancelled_search(qtbot, monkeypatch):
    monkeypatch.setenv(story._ONLINE_PORT_ENV, "8765")
    monkeypatch.setenv(story._ONLINE_INDEX_ENV, "1")
    monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
    entered = Event()

    def late(query, *, consent, port, cancelled, with_index):
        assert consent and with_index
        entered.set()
        assert cancelled.wait(2)
        return online_client.OnlineStoryIndexedResult((), online_client.OnlineStoryIndex(3, 2, 1))

    monkeypatch.setattr(online_client, "search_online", late)
    ui = make_view(qtbot)
    ui.query.setText("старый сюжет")
    qtbot.mouseClick(ui.online_button, LEFT)
    qtbot.waitUntil(entered.is_set)
    ui.query.setText("новый сюжет")
    qtbot.waitUntil(lambda: ui._online_worker is None)
    assert "в индексе" not in ui.scope.text() and "отменён" in ui.status.text()
