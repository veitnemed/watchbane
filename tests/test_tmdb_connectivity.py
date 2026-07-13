from __future__ import annotations

import socket
import ssl
from urllib.error import HTTPError, URLError

import pytest

from apis import tmdb_connectivity


def test_probe_tmdb_dns_detects_localhost_block(monkeypatch) -> None:
    def fake_getaddrinfo(host, port, *_args, **_kwargs):
        del host, port
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(tmdb_connectivity.socket, "getaddrinfo", fake_getaddrinfo)

    result = tmdb_connectivity.probe_tmdb_dns()

    assert result["blocked_localhost"] is True
    assert result["ok"] is False
    assert result["error"] == "dns_blocked"


def test_probe_tmdb_dns_ok_for_public_addresses(monkeypatch) -> None:
    def fake_getaddrinfo(host, port, *_args, **_kwargs):
        del host, port
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("52.84.0.1", 443))]

    monkeypatch.setattr(tmdb_connectivity.socket, "getaddrinfo", fake_getaddrinfo)

    result = tmdb_connectivity.probe_tmdb_dns()

    assert result["blocked_localhost"] is False
    assert result["ok"] is True


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("127.0.0.1", "loopback"),
        ("::1", "loopback"),
        ("0.0.0.0", "unspecified"),
        ("169.254.1.2", "link_local"),
        ("192.168.1.2", "private"),
        ("52.84.0.1", "public_ipv4"),
        ("2600:9000::1", "public_ipv6"),
    ],
)
def test_dns_address_classification(address, expected) -> None:
    assert tmdb_connectivity.classify_dns_address(address) == expected


def test_probe_tmdb_dns_accepts_public_ipv6_only(monkeypatch) -> None:
    monkeypatch.setattr(
        tmdb_connectivity.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2600:9000::1", 443, 0, 0))
        ],
    )

    result = tmdb_connectivity.probe_tmdb_dns()

    assert result["ok"] is True
    assert result["address_classes"] == ["public_ipv6"]


def test_probe_tmdb_dns_rejects_mixed_loopback_and_public(monkeypatch) -> None:
    monkeypatch.setattr(
        tmdb_connectivity.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("52.84.0.1", 443)),
        ],
    )

    result = tmdb_connectivity.probe_tmdb_dns()

    assert result["ok"] is False
    assert result["error"] == "dns_mixed"
    assert result["mixed_public_local"] is True


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (socket.gaierror(getattr(socket, "EAI_NONAME", -2), "not found"), "nxdomain"),
        (socket.timeout("timed out"), "dns_timeout"),
    ],
)
def test_probe_tmdb_dns_distinguishes_resolution_failures(monkeypatch, error, expected) -> None:
    monkeypatch.setattr(
        tmdb_connectivity.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )

    result = tmdb_connectivity.probe_tmdb_dns()

    assert result["ok"] is False
    assert result["error"] == expected


def test_check_tmdb_network_available_stops_on_dns_block(monkeypatch) -> None:
    monkeypatch.setattr(
        tmdb_connectivity,
        "probe_tmdb_dns",
        lambda host=tmdb_connectivity.TMDB_API_HOST: {
            "ok": False,
            "host": host,
            "addresses": ["127.0.0.1"],
            "blocked_localhost": True,
            "error": "dns_blocked",
        },
    )
    calls = {"count": 0}

    def fake_urlopen(*_args, **_kwargs):
        calls["count"] += 1
        raise AssertionError("HTTP probe must not run when DNS is blocked")

    monkeypatch.setattr(tmdb_connectivity, "urlopen", fake_urlopen)

    result = tmdb_connectivity.check_tmdb_network_available()

    assert result["ok"] is False
    assert result["error"] == "dns_blocked"
    assert calls["count"] == 0


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def getcode(self):
        return self.status


@pytest.mark.parametrize("status", [200, 401, 403, 404])
def test_network_probe_treats_http_response_as_reachable(monkeypatch, status) -> None:
    monkeypatch.setattr(
        tmdb_connectivity,
        "probe_tmdb_dns",
        lambda: {"ok": True, "addresses": ["52.84.0.1"]},
    )

    def opener(*_args, **_kwargs):
        if status == 200:
            return _Response()
        raise HTTPError("https://example.invalid", status, "status", {}, None)

    result = tmdb_connectivity.check_tmdb_network_available(opener=opener)

    assert result["ok"] is True
    assert result["http_status"] == status


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (socket.timeout("timed out"), "tcp_timeout"),
        (ssl.SSLError("TLS handshake failed"), "tls_failed"),
        (ssl.SSLCertVerificationError("certificate verify failed"), "certificate_error"),
        (ConnectionRefusedError("refused"), "tcp_failed"),
    ],
)
def test_network_probe_distinguishes_transport_failures(monkeypatch, reason, expected) -> None:
    monkeypatch.setattr(
        tmdb_connectivity,
        "probe_tmdb_dns",
        lambda: {"ok": True, "addresses": ["52.84.0.1"]},
    )

    result = tmdb_connectivity.check_tmdb_network_available(
        opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError(reason))
    )

    assert result["ok"] is False
    assert result["error"] == expected


def test_evaluate_tmdb_startup_readiness_reports_missing_token(monkeypatch) -> None:
    monkeypatch.setattr(
        tmdb_connectivity,
        "check_tmdb_network_available",
        lambda **kwargs: {"ok": True},
    )
    monkeypatch.setattr("apis.tmdb_api.has_tmdb_credentials", lambda: False)

    result = tmdb_connectivity.evaluate_tmdb_startup_readiness()

    assert result["ready"] is False
    assert result["error"] == "missing_token"


def test_evaluate_startup_readiness_checks_network_before_token(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        tmdb_connectivity,
        "check_tmdb_network_available",
        lambda **kwargs: (
            calls.append("network"),
            {"ok": False, "error": "dns_blocked"},
        )[1],
    )
    monkeypatch.setattr(
        "apis.tmdb_api.has_tmdb_credentials",
        lambda: (calls.append("credentials"), True)[1],
    )
    monkeypatch.setattr(
        "apis.tmdb_api.check_api_available",
        lambda token=None: (calls.append("api"), {"ok": True})[1],
    )

    result = tmdb_connectivity.evaluate_tmdb_startup_readiness("secret-token")

    assert result["ready"] is False
    assert result["error"] == "dns_blocked"
    assert calls == ["network"]


def test_evaluate_startup_readiness_converts_unexpected_validation_error(monkeypatch) -> None:
    monkeypatch.setattr(
        tmdb_connectivity,
        "check_tmdb_network_available",
        lambda **kwargs: {"ok": True},
    )
    monkeypatch.setattr(
        "apis.tmdb_api.check_api_available",
        lambda token=None: (_ for _ in ()).throw(ValueError("invalid response")),
    )

    result = tmdb_connectivity.evaluate_tmdb_startup_readiness("wrong-token")

    assert result["ready"] is False
    assert result["error"] == "validation_failed"
    assert "invalid response" in result["details"]
