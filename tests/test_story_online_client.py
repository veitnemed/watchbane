"""Contract checks for the private loopback-only desktop transport."""
from io import BytesIO
import json
from threading import Event

import pytest

from desktop.story import online_client as online


def hit(media="movie", **fields):
    return {"id": f"tmdb:{media}:27", "media_type": media, "title": "Пилот", "year": 2001,
            "overview": "Пилот возвращается домой.", "evidence": "возвращается домой",
            "language": "ru-RU", **fields}


def payload(*rows):
    return json.dumps({"source": "tmdb", "results": rows}, ensure_ascii=False).encode()


class Response:
    def __init__(self, raw, status=200, **headers):
        self.raw = BytesIO(raw)
        self.status = status
        self.headers = {"Content-Type": "application/json", **headers}
        self.closed = False

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read1(self, limit):
        return self.raw.read(limit)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True


@pytest.fixture
def transport(monkeypatch):
    calls = []
    stop = Event()

    class Connection:
        def __init__(self, host, port, timeout):
            calls.append(("create", host, port, timeout))
            self.sock = self
            self.closed = False

        def connect(self):
            calls.append(("connect",))

        def request(self, method, path, data, headers):
            calls.append((method, path, json.loads(data), headers))

        def getresponse(self):
            return self.reply

        def shutdown(self, _how):
            stop.set()

        def close(self):
            calls.append(("close",))
            self.closed = True

    Connection.reply = Response(payload(hit()))
    monkeypatch.setattr(online, "HTTPConnection", Connection)
    return Connection, calls, stop


def test_post_exact_fields_typed_hits_no_ambient_credentials(monkeypatch, transport):
    connection, calls, _ = transport
    connection.reply = Response(payload(hit("movie"), hit("tv")))
    monkeypatch.setenv("HTTP_PROXY", "http://fake-proxy.invalid")
    monkeypatch.setenv("TMDB_TOKEN", "private-key")
    monkeypatch.setenv("WATCHBANE_DATA_DIR", "private-profile")
    results = online.search_online(" пилот ", consent=True, port=32100, limit=2)
    assert [(r.id, r.media_type) for r in results] == [("tmdb:movie:27", "movie"), ("tmdb:tv:27", "tv")]
    assert calls[0][:3] == ("create", "127.0.0.1", 32100)
    assert calls[2][:3] == ("POST", "/v1/search", {"query": "пилот", "limit": 2})
    assert set(calls[2][3]) == {"Content-Type", "Accept", "Accept-Encoding", "Cache-Control"}
    assert all(term not in repr(calls) for term in ("private-key", "private-profile", "fake-proxy"))
    assert connection.reply.closed and calls[-1] == ("close",)


@pytest.mark.parametrize("consent", [False, None, 1, "yes"])
def test_no_network_without_explicit_boolean_consent(transport, consent):
    _, calls, _ = transport
    with pytest.raises(online.OnlineStoryError, match="not authorized"):
        online.search_online("private text", consent=consent)
    assert not calls


@pytest.mark.parametrize("options", [{"port": True}, {"port": 0}, {"limit": 11}, {"limit": True},
                                     {"query": "a" * 601}, {"query": "  "}, {"query": "\ud800"}])
def test_invalid_request_never_opens_transport(transport, options):
    _, calls, _ = transport
    with pytest.raises(online.OnlineStoryError, match="Invalid"):
        online.search_online(consent=True, **({"query": "private"} | options))
    assert not calls


@pytest.mark.parametrize("raw", [
    payload(hit(id="tmdb:tv:27")),
    payload(hit(id=27)),
    payload(hit(id="tmdb:movie:027")),
    payload(hit(id="tmdb:movie:9223372036854775808")),
    payload(hit(), hit()),
    payload(hit(language="en-US")),
    payload(hit(year=True)),
    payload(hit(title="<private>", overview="")),
    b'{"source":"tmdb","source":"tmdb","results":[]}',
    b'{"source":"tmdb","results":[[[[[[]]]]]]}',
    b'{"source":"tmdb","results":[],"private-role":"unexpected"}',
])
def test_untrusted_response_is_all_or_nothing_and_never_echoes(transport, raw):
    connection, _, _ = transport
    connection.reply = Response(raw)
    with pytest.raises(online.OnlineStoryError, match="^Invalid response from the local story server[.]$"):
        online.search_online("never echo", consent=True)


def test_nominal_empty_and_bounded_result_count(transport):
    connection, _, _ = transport
    connection.reply = Response(payload())
    assert online.search_online("query", consent=True) == ()
    connection.reply = Response(payload(hit(), hit("tv")))
    with pytest.raises(online.OnlineStoryError, match="Invalid response"):
        online.search_online("query", consent=True, limit=1)


@pytest.mark.parametrize("headers", [
    {"Content-Type": "text/html"},
    {"Content-Length": str(online._MAX_BYTES + 1)},
    {"Content-Length": "1, 1"},
    {"Content-Length": "1"},
    {"Content-Encoding": "gzip"},
    {},
])
def test_bad_headers_or_oversize_stream_fail_closed(transport, headers):
    connection, _, _ = transport
    raw = payload() if headers else b"x" * (online._MAX_BYTES + 1)
    connection.reply = Response(raw, **headers)
    with pytest.raises(online.OnlineStoryError, match="Invalid response"):
        online.search_online("query", consent=True)


def test_redirect_status_never_follows_location(transport):
    connection, calls, _ = transport
    connection.reply = Response(b"private failure", status=307, Location="https://external.invalid/")
    with pytest.raises(online.OnlineStoryError, match="unavailable"):
        online.search_online("query", consent=True)
    assert [call[0] for call in calls] == ["create", "connect", "POST", "close"]


def test_pre_cancel_and_cancel_while_waiting_for_a_blocked_read(transport, monkeypatch):
    connection, calls, stopped = transport
    cancel = Event()
    cancel.set()
    with pytest.raises(online.OnlineStoryError, match="cancelled"):
        online.search_online("query", consent=True, cancelled=cancel)
    assert not calls
    cancel.clear()

    def blocked_read(_limit):
        cancel.set()
        assert stopped.wait(2)
        return b""

    monkeypatch.setattr(connection.reply, "read1", blocked_read)
    with pytest.raises(online.OnlineStoryError, match="cancelled"):
        online.search_online("query", consent=True, cancelled=cancel)
    assert connection.reply.closed and calls[-1] == ("close",)


def test_cancellation_just_before_consumer_gets_parsed_result(transport, monkeypatch):
    cancel = Event()
    parse = online._parse

    def superseded(*args):
        result = parse(*args)
        cancel.set()
        return result

    monkeypatch.setattr(online, "_parse", superseded)
    with pytest.raises(online.OnlineStoryError, match="cancelled"):
        online.search_online("query", consent=True, cancelled=cancel)


def test_absolute_timeout_interrupts_blocked_headers(transport, monkeypatch):
    connection, _, stopped = transport
    monkeypatch.setattr(online, "_TIMEOUT", .08)

    def blocked_headers(_self):
        assert stopped.wait(2)
        raise OSError("private transport details")

    monkeypatch.setattr(connection, "getresponse", blocked_headers)
    with pytest.raises(online.OnlineStoryError, match="^Local story search timed out[.]$"):
        online.search_online("private", consent=True)


def test_real_http_roundtrip_over_ipv4_loopback():
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread

    received = []
    response = payload(hit("tv"))

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            data = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, json.loads(data), self.headers.get("Authorization"), self.headers.get("Cookie")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(response)

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
            result = online.search_online("пилот", consent=True, port=server.server_port, limit=1)
            assert result[0].id == "tmdb:tv:27"
            assert received == [("/v1/search", {"query": "пилот", "limit": 1}, None, None)]
        finally:
            server.shutdown()
            worker.join()


@pytest.mark.parametrize(("status", "body", "headers", "busy"), [
    (503, b'{"detail":"search_busy"}', {}, True),
    (503, b'{"detail":"search_busy"}', {"Content-Length": "24"}, True),
    (502, b'{"detail":"search_busy"}', {}, False),
    (503, b'{"detail":"search_unavailable"}', {}, False),
    (503, b'{"detail":"search_busy","detail":"search_busy"}', {}, False),
    (503, b'{"detail":"search_busy","private":"not-an-error-field"}', {}, False),
    (503, b'{"detail":"search_busy"}' + b" " * 256, {}, False),
    (503, b'{"detail":"search_busy"}', {"Content-Type": "text/plain"}, False),
    (503, b'{"detail":"search_busy"}', {"Content-Encoding": "gzip"}, False),
    (503, b'{"detail":"search_busy"}', {"Content-Length": "25"}, False),
    (503, b'{"detail":"search_busy"}', {"Content-Length": "257"}, False),
])
def test_only_bounded_exact_search_busy_503_has_typed_error(transport, status, body, headers, busy):
    connection, calls, _ = transport
    connection.reply = Response(body, status=status, **headers)
    with pytest.raises(online.OnlineStoryError) as captured:
        online.search_online("never echo", consent=True, with_outcome=True)
    assert isinstance(captured.value, online.OnlineStoryBusy) is busy
    assert "private" not in str(captured.value) and "never echo" not in str(captured.value)
    assert [call[0] for call in calls] == ["create", "connect", "POST", "close"]


_RATE_BODY = b'{"detail":"search_rate_limited"}'


@pytest.mark.parametrize("seconds", ["1", "7", "59", "60"])
def test_rate_limited_429_is_typed_without_negotiated_success_headers(transport, seconds):
    connection, calls, _ = transport
    connection.reply = Response(_RATE_BODY, status=429,
                                **{"Cache-Control": "no-store", "Retry-After": seconds})
    with pytest.raises(online.OnlineStoryRateLimited) as captured:
        online.search_online("never echo", consent=True, with_outcome=True, with_index=True, with_artwork=True)
    assert captured.value.retry_after == int(seconds) and "never echo" not in str(captured.value)
    assert [call[0] for call in calls] == ["create", "connect", "POST", "close"]


@pytest.mark.parametrize("body,headers", [
    (_RATE_BODY, {"Retry-After": ""}),
    (_RATE_BODY, {"Retry-After": "0"}),
    (_RATE_BODY, {"Retry-After": "61"}),
    (_RATE_BODY, {"Retry-After": "2, 2"}),
    (_RATE_BODY, {"Retry-After": "07"}),
    (_RATE_BODY, {"Retry-After": "+7"}),
    (_RATE_BODY, {"Retry-After": "٧"}),
    (_RATE_BODY, {"Retry-After": "Sun, 22 Nov 2026 11:00:00 GMT"}),
    (_RATE_BODY, {"Cache-Control": "private"}),
    (_RATE_BODY, {"Content-Encoding": "gzip"}),
    (_RATE_BODY, {"Content-Type": "text/plain"}),
    (_RATE_BODY, {"Content-Length": "999"}),
    (_RATE_BODY + b" " * 256, {}),
    (b'{"detail":"search_rate_limited","detail":"search_rate_limited"}', {}),
    (b'{"detail":"search_rate_limited","opaque":"private-value"}', {}),
    (b'{"detail":"search_busy"}', {}),
])
def test_malformed_or_oversized_429_stays_generic_without_retry(transport, body, headers):
    connection, calls, _ = transport
    connection.reply = Response(body, status=429, **({"Cache-Control": "no-store", "Retry-After": "7"} | headers))
    with pytest.raises(online.OnlineStoryError) as captured:
        online.search_online("private-query", consent=True)
    assert type(captured.value) is online.OnlineStoryError
    assert "private" not in str(captured.value)
    assert [call[0] for call in calls] == ["create", "connect", "POST", "close"]


def test_cancellation_while_reading_429_suppresses_typed_cooldown(transport):
    connection, _, _ = transport
    cancelled = Event()

    class CancelledReply(Response):
        def read1(self, limit):
            data = super().read1(limit)
            cancelled.set()
            return data

    connection.reply = CancelledReply(_RATE_BODY, status=429,
                                      **{"Cache-Control": "no-store", "Retry-After": "7"})
    with pytest.raises(online.OnlineStoryError, match="cancelled") as captured:
        online.search_online("private-query", consent=True, cancelled=cancelled)
    assert type(captured.value) is online.OnlineStoryError
