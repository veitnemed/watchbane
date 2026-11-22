from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread, current_thread, main_thread

import pytest

from tools.qa import story_search_pressure as pressure


@contextmanager
def server(status, headers, body):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as httpd:
        worker = Thread(target=httpd.serve_forever, args=(.01,))
        worker.start()
        try:
            yield httpd.server_port
        finally:
            httpd.shutdown()
            worker.join(2)


@pytest.mark.parametrize("status,body,header,outcome", [
    (200, {"results": []}, {}, "ok"),
    (503, {"detail": "search_busy"}, {"Retry-After": "1"}, "busy_503"),
    (503, {"detail": "search_unavailable"}, {"Retry-After": "1"}, "unknown"),
    (503, {"detail": "search_busy"}, {"Retry-After": "60"}, "unknown"),
    (429, {}, {}, "rate_limited_429"),
    (418, {}, {}, "unknown"),
])
def test_exchange_distinguishes_busy_rate_limit_and_unknown(status, body, header, outcome):
    with server(status, {"Cache-Control": "no-store", **header}, json.dumps(body).encode()) as port:
        assert pressure.exchange(port, b"{}") == (outcome, body if outcome == "ok" else None)


def test_exchange_rejects_missing_cache_control_and_oversize_busy_document():
    with server(200, {}, b"{}") as port:
        assert pressure.exchange(port, b"{}") == ("unknown", None)
    with server(503, {"Cache-Control": "no-store", "Retry-After": "1"}, b" " * 256 + b"{}") as port:
        assert pressure.exchange(port, b"{}") == ("unknown", None)


def test_all_success_without_observed_pressure_does_not_pass():
    result = pressure.pressure_report(0, [b"test"], [0], int, send=lambda *_: ("ok", 0))
    assert not result["passed"] and result["counts"]["ok"] == 18
    assert result["recovery_successes"] == 3


def test_mismatched_success_busy_unknown_and_recovery_accounted(monkeypatch):
    monkeypatch.setattr(pressure, "_CONCURRENCY", 3)

    def send(_port, body):
        if current_thread() is main_thread():
            return "unknown", None
        return {b"test": ("ok", 1), b"limit": ("rate_limited_429", None),
                b"busy": ("busy_503", None)}[body]

    result = pressure.pressure_report(0, [b"test", b"limit", b"busy"], [0, 0, 0], int, send=send)
    assert not result["passed"] and result["successful_order_mismatches"] == 3
    assert result["recovery_successes"] == 0
    assert result["counts"] == {"ok": 3, "busy_503": 3, "rate_limited_429": 3, "unknown": 0}
