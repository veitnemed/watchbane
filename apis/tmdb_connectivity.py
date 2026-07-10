"""TMDb DNS and network reachability checks for desktop startup gate."""

from __future__ import annotations

import socket
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apis import tmdb_api

TMDB_API_HOST = "api.themoviedb.org"
TMDB_CONFIGURATION_URL = f"{tmdb_api.API_URL}/configuration"
NETWORK_PROBE_TIMEOUT_SECONDS = 8


def _is_localhost_address(address: str) -> bool:
    normalized = str(address or "").strip().casefold()
    return normalized == "::1" or normalized.startswith("127.")


def probe_tmdb_dns(host: str = TMDB_API_HOST) -> dict[str, Any]:
    """Resolve TMDb API host and detect localhost DNS hijacks."""
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = sorted({str(info[4][0]) for info in infos})
        blocked_localhost = any(_is_localhost_address(address) for address in addresses)
        return {
            "ok": blocked_localhost is False and len(addresses) > 0,
            "host": host,
            "addresses": addresses,
            "blocked_localhost": blocked_localhost,
            "error": "dns_blocked" if blocked_localhost else None,
        }
    except OSError as error:
        return {
            "ok": False,
            "host": host,
            "addresses": [],
            "blocked_localhost": False,
            "error": "dns_failed",
            "details": str(error),
        }


def check_tmdb_network_available(*, opener=None) -> dict[str, Any]:
    """Check DNS and HTTPS reachability before token validation."""
    started = time.monotonic()
    dns = probe_tmdb_dns()
    if dns.get("blocked_localhost"):
        return {
            "ok": False,
            "error": "dns_blocked",
            "dns": dns,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        }
    if dns.get("ok") is not True:
        return {
            "ok": False,
            "error": dns.get("error") or "dns_failed",
            "dns": dns,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        }

    active_opener = opener or urlopen
    request = Request(
        TMDB_CONFIGURATION_URL,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with active_opener(request, timeout=NETWORK_PROBE_TIMEOUT_SECONDS) as response:
            status_code = getattr(response, "status", None) or response.getcode()
        reachable = int(status_code) in (200, 401)
        return {
            "ok": reachable,
            "error": None if reachable else "network_unreachable",
            "dns": dns,
            "http_status": int(status_code),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except HTTPError as error:
        reachable = int(error.code) in (200, 401)
        return {
            "ok": reachable,
            "error": None if reachable else "network_unreachable",
            "dns": dns,
            "http_status": int(error.code),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except (URLError, TimeoutError, OSError) as error:
        return {
            "ok": False,
            "error": "network_unreachable",
            "dns": dns,
            "details": str(error),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        }


def evaluate_tmdb_startup_readiness(token: str | None = None) -> dict[str, Any]:
    """Network check first, then credentials and API ping."""
    network = check_tmdb_network_available()
    if network.get("ok") is not True:
        return {
            "ready": False,
            "error": network.get("error") or "network_unreachable",
            "network": network,
        }

    normalized_token = str(token or "").strip()
    if normalized_token == "":
        if tmdb_api.has_tmdb_credentials() is False:
            return {
                "ready": False,
                "error": "missing_token",
                "network": network,
            }
        api = tmdb_api.check_api_available()
    else:
        api = tmdb_api.check_api_available(token=normalized_token)

    if api.get("ok") is True:
        return {
            "ready": True,
            "error": None,
            "network": network,
            "api": api,
        }

    return {
        "ready": False,
        "error": "invalid_token",
        "network": network,
        "api": api,
        "details": api.get("details") or api.get("error"),
    }
