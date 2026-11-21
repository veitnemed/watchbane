from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from threading import Thread

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMessageBox

from desktop.story.online_client import OnlineStoryError, OnlineStoryOutcome, search_online
from desktop.story import view as story


HEADER = "Watchbane-Search-Outcome"
MATCH = ("candidates", "possible_local_results")
EMPTY = (
    ("scope_refusal", "explicit_non_film_request", "только фильмы и сериалы"),
    ("clarification", "unsupported_exclusion", "не проверяет исключения"),
    ("clarification", "need_plot_detail", "Добавьте деталь"),
    ("clarification", "no_eligible_catalog_entries", "нет описаний"),
    ("clarification", "no_candidates", "не нашёл вариантов"),
)
HIT = {"id": "tmdb:tv:1384", "media_type": "tv", "title": "Контроль", "year": 2020,
       "overview": "Детектив раскрывает загадку.", "evidence": "раскрывает загадку", "language": "ru-RU"}


def outcome(state=None, reason=None, *, results=()):
    body = {"source": "tmdb", "results": list(results)}
    if state is not None:
        body["outcome"] = {"state": state, "reason": reason}
    return body


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.server.requests.append((self.path, self.headers.get(HEADER), data))
            raw = json.dumps(self.server.response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            for value in self.server.echo:
                self.send_header(HEADER, value)
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass  # client rejects an incompatible header before reading
        def log_message(self, *_args):
            pass

    try:
        http = HTTPServer(("127.0.0.1", 0), Handler)
    except PermissionError:
        pytest.skip("Execution sandbox does not permit loopback sockets")
    with http:
        http.requests = []
        http.response, http.echo = outcome(), ()
        worker = Thread(target=http.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
        worker.start()
        try:
            yield http
        finally:
            http.shutdown()
            worker.join()


def test_legacy_default_unchanged_and_negotiated_candidates_keep_typed_results(server):
    server.response = outcome(results=[HIT])
    legacy = search_online("test", consent=True, port=server.server_port)
    assert type(legacy) is tuple and legacy[0].id == HIT["id"]
    assert server.requests == [("/v1/search", None, {"query": "test", "limit": 5})]
    server.response = outcome(*MATCH, results=[HIT])
    server.echo = ("1",)
    modern = search_online("test", consent=True, port=server.server_port, with_outcome=True)
    assert modern == OnlineStoryOutcome(legacy, *MATCH)
    assert server.requests[-1] == ("/v1/search", "1", {"query": "test", "limit": 5})


@pytest.mark.parametrize("echo,response", [
    ((), outcome()), (("2",), outcome(*MATCH, results=[HIT])),
    (("1", "1"), outcome(*MATCH, results=[HIT])),
    (("1",), outcome()), (("1",), outcome("clarification", "server-supplied private text")),
    (("1",), outcome("clarification", "explicit_non_film_request")),
    (("1",), outcome(*MATCH)), (("1",), outcome("clarification", "no_candidates", results=[HIT])),
    (("1",), outcome("clarification", ["no_candidates"])),
])
def test_negotiation_refuses_invalid_echo_body_and_never_retries(server, echo, response):
    server.echo, server.response = echo, response
    with pytest.raises(OnlineStoryError, match="^Invalid response from the local story server[.]$"):
        search_online("private input", consent=True, port=server.server_port, with_outcome=True)
    assert server.requests == [("/v1/search", "1", {"query": "private input", "limit": 5})]


def view_request(qtbot, monkeypatch, server, flag):
    monkeypatch.setenv(story._ONLINE_PORT_ENV, str(server.server_port))
    monkeypatch.setenv(story._ONLINE_OUTCOME_ENV, flag)
    monkeypatch.setattr(QMessageBox, "exec", lambda _dialog: QMessageBox.StandardButton.Yes)
    widget = story.StorySearchView()
    qtbot.addWidget(widget.widget)
    widget.widget.show()
    widget.query.setText("контрольный запрос")
    widget.on_tab_activated()
    assert not server.requests
    qtbot.mouseClick(widget.online_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: widget._online_worker is None)
    return widget


@pytest.mark.parametrize("state,reason,text", EMPTY)
def test_gui_distinguishes_negotiated_empty_results_without_cards(qtbot, monkeypatch, server, state, reason, text):
    server.response = outcome(state, reason)
    server.echo = ("1",)
    widget = view_request(qtbot, monkeypatch, server, "1")
    assert text in widget.status.text()
    assert reason not in widget.status.text()
    assert widget.cards_layout.count() == 1 and not widget._records
    assert len(server.requests) == 1 and server.requests[0][1] == "1"


def test_gui_flag_is_exact_and_legacy_server_not_retried(qtbot, monkeypatch, server):
    legacy = view_request(qtbot, monkeypatch, server, "yes")
    assert "не нашёл вариантов" in legacy.status.text() and server.requests[0][1] is None
    server.requests.clear()
    modern = view_request(qtbot, monkeypatch, server, "1")
    assert "не ответил или вернул ошибку" in modern.status.text()
    assert modern.cards_layout.count() == 1
    assert len(server.requests) == 1 and server.requests[0][1] == "1"


def test_gui_negotiated_candidates_render_without_altering_card_identity(qtbot, monkeypatch, server):
    server.response, server.echo = outcome(*MATCH, results=[HIT]), ("1",)
    widget = view_request(qtbot, monkeypatch, server, "1")
    assert widget.cards.findChild(QLabel, "storyTitle").text() == "Контроль"
    assert widget._records["tmdb:tv:1384"]["media_type"] == "tv"
