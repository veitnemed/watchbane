"""TMDb DNS and network reachability checks for desktop startup gate."""

from __future__ import annotations

import ipaddress
import socket
import ssl
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apis import tmdb_api

TMDB_API_HOST = "api.themoviedb.org"
TMDB_CONFIGURATION_URL = f"{tmdb_api.API_URL}/configuration"
NETWORK_PROBE_TIMEOUT_SECONDS = 8


def classify_dns_address(address: str) -> str:
    """Classify one DNS answer without treating private/local routes as public TMDb."""
    try:
        value = ipaddress.ip_address(str(address or "").strip())
    except ValueError:
        return "invalid"
    if value.is_loopback:
        return "loopback"
    if value.is_unspecified:
        return "unspecified"
    if value.is_link_local:
        return "link_local"
    if value.is_private:
        return "private"
    return "public_ipv4" if value.version == 4 else "public_ipv6"


def _classify_dns_failure(error: OSError) -> str:
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "dns_timeout"
    if isinstance(error, socket.gaierror) and getattr(error, "errno", None) in {
        getattr(socket, "EAI_NONAME", None),
        getattr(socket, "EAI_NODATA", None),
    }:
        return "nxdomain"
    return "dns_failed"


def probe_tmdb_dns(host: str = TMDB_API_HOST) -> dict[str, Any]:
    """Resolve TMDb API host and detect localhost DNS hijacks."""
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = sorted({str(info[4][0]) for info in infos})
        address_classes = [classify_dns_address(address) for address in addresses]
        public = any(value in {"public_ipv4", "public_ipv6"} for value in address_classes)
        blocked_localhost = any(value in {"loopback", "unspecified"} for value in address_classes)
        mixed = blocked_localhost and public
        error = "dns_mixed" if mixed else "dns_blocked" if blocked_localhost else None
        if error is None and public is False:
            error = "dns_non_public"
        return {
            "ok": error is None and len(addresses) > 0,
            "host": host,
            "addresses": addresses,
            "address_classes": address_classes,
            "blocked_localhost": blocked_localhost,
            "mixed_public_local": mixed,
            "error": error,
        }
    except OSError as error:
        return {
            "ok": False,
            "host": host,
            "addresses": [],
            "blocked_localhost": False,
            "error": _classify_dns_failure(error),
            "details": str(error),
        }


def _classify_network_exception(error: BaseException) -> str:
    reason = getattr(error, "reason", error)
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "tcp_timeout"
    if isinstance(reason, ssl.SSLCertVerificationError):
        return "certificate_error"
    if isinstance(reason, ssl.SSLError):
        return "tls_failed"
    if isinstance(reason, socket.gaierror):
        return _classify_dns_failure(reason)
    if isinstance(reason, (ConnectionError, ConnectionRefusedError)):
        return "tcp_failed"
    text = str(reason).casefold()
    if "certificate" in text or "cert_verify" in text:
        return "certificate_error"
    if "ssl" in text or "tls" in text:
        return "tls_failed"
    if "timed out" in text or "timeout" in text:
        return "tcp_timeout"
    return "network_unreachable"


def check_tmdb_network_available(*, opener=None) -> dict[str, Any]:
    """Check DNS and HTTPS reachability before token validation."""
    started = time.monotonic()
    dns = probe_tmdb_dns()
    if dns.get("blocked_localhost"):
        return {
            "ok": False,
            "error": dns.get("error") or "dns_blocked",
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
        reachable = int(status_code) in (200, 401, 403, 404)
        return {
            "ok": reachable,
            "error": None if reachable else "network_unreachable",
            "dns": dns,
            "http_status": int(status_code),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except HTTPError as error:
        reachable = int(error.code) in (200, 401, 403, 404)
        return {
            "ok": reachable,
            "error": None if reachable else "network_unreachable",
            "dns": dns,
            "http_status": int(error.code),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except (URLError, TimeoutError, OSError, ssl.SSLError) as error:
        error_code = _classify_network_exception(error)
        return {
            "ok": False,
            "error": error_code,
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
    try:
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
    except Exception as error:  # noqa: BLE001 - startup callers require a result contract
        return {
            "ready": False,
            "error": "validation_failed",
            "network": network,
            "details": str(error),
        }

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
