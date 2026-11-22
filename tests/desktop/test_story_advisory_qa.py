"""QA-only rehearsal: deliberately advise on every nonempty online response."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread

import pytest
from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QLabel, QMessageBox, QPushButton

from candidates.title_state_service import STATE_WATCHLIST, get_title_state
from desktop.story import view as story


class _HideGuard(QObject):
    def __init__(self, view):
        super().__init__(view.widget)
        self.view = view

    def eventFilter(self, _obj, event):
        if event.type() in (QEvent.Type.Hide, QEvent.Type.Close):
            self.view._cancel_online_search()
        return False


class _AdvisoryView(story.StorySearchView):
    """Intercept the real rendering boundary, before any collection access."""

    def __init__(self):
        self.stage = None
        self.reveal = None
        super().__init__()
        self.reveal = QPushButton("Показать варианты", self.widget)
        self.reveal.clicked.connect(self._reveal_advised)
        self.widget.layout().insertWidget(self.widget.layout().indexOf(self.status) + 1, self.reveal)
        self.reveal.hide()
        self.query.textChanged.connect(self._discard_advice)
        self._hide_guard = _HideGuard(self)
        self.widget.installEventFilter(self._hide_guard)

    def _discard_advice(self, *_):
        self.stage = None
        if self.reveal is not None:
            self.reveal.hide()

    def _clear(self):
        self._discard_advice()
        super()._clear()

    def _cancel_online_search(self):
        self._discard_advice()
        super()._cancel_online_search()

    def prepare_for_shutdown(self):
        self._discard_advice()
        super().prepare_for_shutdown()

    def _render_cards(self, hits, records, *, online=False, online_artwork=None):
        if not online or not hits:
            return super()._render_cards(hits, records, online=online, online_artwork=online_artwork)
        if self._closing or not self.widget.isVisible():
            return
        self.stage = (self.query.text(), tuple(hits), json.dumps(records), tuple((online_artwork or {}).items()))
        self.status.setText("Ищете фильм или сериал? Можно уточнить сюжет или посмотреть найденные варианты.")
        self.reveal.show()

    def _reveal_advised(self):
        stage = self.stage
        self._discard_advice()
        if stage is None or self._closing or not self.widget.isVisible() or stage[0] != self.query.text():
            return
        _, hits, records, artwork = stage
        self.status.setText(f"Варианты с тестового сервера: {len(hits)}")
        super()._render_cards(hits, json.loads(records), online=True, online_artwork=dict(artwork))


@pytest.fixture
def loopback(monkeypatch):
    sent, ready, release = [], Event(), Event()
    rows = [
        {"id": f"tmdb:{media}:7144", "media_type": media, "title": f"Карточка {media}",
         "year": 2021, "overview": "Контрольный сюжет.", "evidence": "Контрольный", "language": "ru-RU"}
        for media in ("movie", "tv")
    ]
    body = json.dumps({"source": "tmdb", "results": rows}).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            sent.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            ready.set()
            release.wait(2)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *_):
            pass

    try:
        server = HTTPServer(("127.0.0.1", 0), Handler)
    except PermissionError:
        pytest.skip("loopback is unavailable")
    with server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
        thread.start()
        try:
            monkeypatch.setenv(story._ONLINE_PORT_ENV, str(server.server_port))
            for name in (story._ONLINE_OUTCOME_ENV, story._ONLINE_ARTWORK_ENV, story._ONLINE_INDEX_ENV):
                monkeypatch.delenv(name, raising=False)
            yield sent, ready, release
        finally:
            release.set()
            server.shutdown()
            thread.join()


def _view(qtbot):
    view = _AdvisoryView()
    qtbot.addWidget(view.widget)
    view.widget.resize(1100, 850)
    view.widget.show()
    view.query.setText("поезд выходит из тоннеля")
    return view


def test_advised_consent_reveal_and_real_save(qtbot, monkeypatch, loopback):
    sent, _, release = loopback
    release.set()
    prompts, reads, writes = [], [], []
    decisions = iter((QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes))

    def consent(dialog):
        prompts.append(dialog.defaultButton().text())
        return next(decisions)

    monkeypatch.setattr(QMessageBox, "exec", consent)
    original = story.get_title_states
    monkeypatch.setattr(story, "get_title_states", lambda rows: reads.append(tuple(rows)) or original(rows))
    save = story.service.add_candidate_to_watchlist
    monkeypatch.setattr(story.service, "add_candidate_to_watchlist",
                        lambda row: writes.append((row["media_type"], row["tmdb_id"])) or save(row))
    view = _view(qtbot)
    view.online_button.click()
    assert len(prompts) == 1 and not sent and view._online_worker is None
    view.online_button.click()
    qtbot.waitUntil(lambda: view.stage is not None)
    assert len(prompts) == 2 and sent == [("/v1/search", {"query": view.query.text(), "limit": 5})]
    assert not reads and not writes and not view._records and not view.cards.findChildren(QPushButton, "storySaveAction")
    tv = {"tmdb_id": 7144, "media_type": "tv", "title": "Карточка tv"}
    assert get_title_state(tv) != STATE_WATCHLIST
    qtbot.keyClick(view.reveal, Qt.Key.Key_Space)
    assert [title.text() for title in view.cards.findChildren(QLabel, "storyTitle")] == [
        "Карточка movie", "Карточка tv"]
    typed = ("tmdb:movie:7144", "tmdb:tv:7144")
    assert tuple(view._records) == typed and reads == [typed]
    buttons = view.cards.findChildren(QPushButton, "storySaveAction")
    assert len(buttons) == 2
    assert not writes
    buttons[1].click()
    assert writes == [("tv", 7144)]
    assert get_title_state(tv) == STATE_WATCHLIST
    assert get_title_state(dict(tv, media_type="movie", title="Карточка movie")) != STATE_WATCHLIST
    view._reveal_advised()
    assert len(prompts) == 2 and len(sent) == 1 and reads == [typed] and view.stage is None


@pytest.mark.parametrize("event", ["edit", "cancel", "hide", "shutdown", "stale", "stale-hide"])
def test_advised_candidates_are_disposed_without_render(qtbot, monkeypatch, loopback, event):
    sent, ready, release = loopback
    monkeypatch.setattr(QMessageBox, "exec", lambda *_: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(story, "get_title_states", lambda *_: pytest.fail("undisclosed collection access"))
    view = _view(qtbot)
    old = view.query.text()
    view.online_button.click()
    qtbot.waitUntil(ready.is_set)
    if event.startswith("stale"):
        if event == "stale-hide":
            view.widget.hide()
            view.widget.show()
        else:
            view.query.setText("другой")
            view.query.setText(old)
        release.set()
        qtbot.waitUntil(lambda: view._online_worker is None)
    else:
        release.set()
        qtbot.waitUntil(lambda: view.stage is not None)
        if event == "edit":
            view.query.setText("другой")
            view.query.setText(old)
        elif event == "cancel":
            view._cancel_online_search()
        elif event == "hide":
            view.widget.hide()
            view.widget.show()
        else:
            view.prepare_for_shutdown()
    view._reveal_advised()
    assert len(sent) == 1
    assert view.stage is None and view.reveal.isHidden() and not view._records
    assert not view.cards.findChildren(QLabel, "storyTitle")
