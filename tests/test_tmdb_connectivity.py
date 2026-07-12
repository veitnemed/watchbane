from __future__ import annotations

import socket

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
