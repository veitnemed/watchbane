"""Write a detailed temporary TMDb network diagnostic log.

This script does not use TMDB_TOKEN. It probes only public endpoints that should
return either HTTP 200/401/404 if the network path is healthy enough to reach
TMDb.
"""

from __future__ import annotations

import json
import os
import platform
import socket
import ssl
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener, getproxies, urlopen


ROOT_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT_DIR / "reports" / "network"
HOSTS = ("api.themoviedb.org", "www.themoviedb.org")
URLS = (
    "https://api.themoviedb.org/3/configuration",
    "https://www.themoviedb.org/",
    "https://www.google.com/",
)
POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def redact_proxy(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if value == "":
        return "-"
    parsed = urlsplit(value if "://" in value else f"http://{value}")
    host = parsed.hostname or value
    port = f":{parsed.port}" if parsed.port else ""
    scheme = parsed.scheme or "http"
    return f"{scheme}://{host}{port}"


def section(lines: list[str], title: str) -> None:
    lines.append("")
    lines.append("=" * 80)
    lines.append(title)
    lines.append("=" * 80)


def append_kv(lines: list[str], key: str, value: Any) -> None:
    lines.append(f"{key}: {value}")


def run_command(lines: list[str], title: str, command: list[str], timeout: int = 20) -> None:
    section(lines, title)
    lines.append(f"$ {' '.join(command)}")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except Exception as error:
        lines.append(f"COMMAND_ERROR: {type(error).__name__}: {error}")
        return

    elapsed = time.monotonic() - started
    append_kv(lines, "exit_code", completed.returncode)
    append_kv(lines, "elapsed_sec", f"{elapsed:.2f}")
    if completed.stdout.strip():
        lines.append("-- stdout --")
        lines.append(completed.stdout.rstrip())
    if completed.stderr.strip():
        lines.append("-- stderr --")
        lines.append(completed.stderr.rstrip())


def dns_probe(lines: list[str]) -> None:
    section(lines, "Python socket DNS")
    for host in HOSTS:
        lines.append(f"[{host}]")
        try:
            infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            addresses = sorted({str(info[4][0]) for info in infos})
            lines.append(f"addresses: {', '.join(addresses) if addresses else '-'}")
            if any(address == "::1" or address.startswith("127.") for address in addresses):
                lines.append("warning: resolves to localhost")
        except Exception as error:
            lines.append(f"error: {type(error).__name__}: {error}")


def tcp_probe(lines: list[str]) -> None:
    section(lines, "TCP connect to resolved addresses")
    for host in HOSTS:
        lines.append(f"[{host}]")
        try:
            infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except Exception as error:
            lines.append(f"dns_error: {type(error).__name__}: {error}")
            continue

        tested: set[tuple[str, int]] = set()
        for info in infos:
            address = str(info[4][0])
            port = int(info[4][1])
            key = (address, port)
            if key in tested:
                continue
            tested.add(key)
            started = time.monotonic()
            sock = socket.socket(info[0], socket.SOCK_STREAM)
            sock.settimeout(8)
            try:
                sock.connect(info[4])
                elapsed = time.monotonic() - started
                lines.append(f"{address}:{port} OK {elapsed:.2f}s")
            except Exception as error:
                elapsed = time.monotonic() - started
                lines.append(f"{address}:{port} FAIL {elapsed:.2f}s {type(error).__name__}: {error}")
            finally:
                sock.close()


def http_probe(lines: list[str], title: str, opener_factory) -> None:
    section(lines, title)
    for url in URLS:
        request = Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
                "User-Agent": "tmdb-network-probe/1.0",
            },
        )
        started = time.monotonic()
        lines.append(f"[{url}]")
        try:
            opener = opener_factory()
            with opener.open(request, timeout=20) as response:
                raw = response.read(256)
            elapsed = time.monotonic() - started
            lines.append(f"OK status={response.status} elapsed={elapsed:.2f}s bytes_sample={len(raw)}")
            lines.append(f"final_url={response.geturl()}")
            lines.append(f"headers={dict(response.headers.items())}")
        except HTTPError as error:
            elapsed = time.monotonic() - started
            body = error.read(512).decode("utf-8", errors="replace")
            lines.append(f"HTTP_ERROR status={error.code} elapsed={elapsed:.2f}s reason={error.reason}")
            lines.append(f"body_sample={body}")
        except URLError as error:
            elapsed = time.monotonic() - started
            lines.append(f"URL_ERROR elapsed={elapsed:.2f}s reason={repr(error.reason)}")
            lines.append(traceback.format_exc().rstrip())
        except Exception as error:
            elapsed = time.monotonic() - started
            lines.append(f"ERROR elapsed={elapsed:.2f}s {type(error).__name__}: {error}")
            lines.append(traceback.format_exc().rstrip())


def doh_probe(lines: list[str]) -> None:
    section(lines, "DNS over HTTPS via dns.google")
    for host in HOSTS:
        query = urlencode({"name": host, "type": "A"})
        url = f"https://dns.google/resolve?{query}"
        request = Request(url, headers={"Accept": "application/dns-json"})
        lines.append(f"[{host}] {url}")
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            answers = payload.get("Answer") or []
            lines.append(json.dumps(answers, ensure_ascii=False))
        except Exception as error:
            lines.append(f"error: {type(error).__name__}: {error}")


def environment_probe(lines: list[str]) -> None:
    section(lines, "Environment")
    append_kv(lines, "created_at", now())
    append_kv(lines, "cwd", ROOT_DIR)
    append_kv(lines, "python", sys.version.replace("\n", " "))
    append_kv(lines, "openssl", ssl.OPENSSL_VERSION)
    append_kv(lines, "platform", platform.platform())

    proxies = getproxies()
    safe_proxies = {key: redact_proxy(value) for key, value in sorted(proxies.items())}
    append_kv(lines, "urllib_getproxies", safe_proxies if safe_proxies else "none")

    proxy_env = {
        key: redact_proxy(value)
        for key, value in sorted(os.environ.items())
        if "proxy" in key.lower()
    }
    append_kv(lines, "proxy_env", proxy_env if proxy_env else "none")


def write_log() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"tmdb_network_probe_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    lines: list[str] = ["TMDb network probe"]

    environment_probe(lines)
    dns_probe(lines)
    tcp_probe(lines)

    http_probe(lines, "HTTPS via Python default opener", lambda: build_opener())
    http_probe(lines, "HTTPS via Python no-proxy opener", lambda: build_opener(ProxyHandler({})))
    doh_probe(lines)

    run_command(lines, "Resolve-DnsName api.themoviedb.org", ["Resolve-DnsName", "api.themoviedb.org"])
    run_command(lines, "Resolve-DnsName www.themoviedb.org", ["Resolve-DnsName", "www.themoviedb.org"])
    run_command(lines, "ipconfig /all", ["ipconfig", "/all"])
    run_command(lines, "ipconfig /displaydns themoviedb", ["ipconfig", "/displaydns"])
    run_command(lines, "netstat port 10809", ["netstat", "-ano"])
    run_command(
        lines,
        "Happ/xray/sing-box services",
        [
            POWERSHELL,
            "-NoProfile",
            "-Command",
            "Get-Service | Where-Object { $_.Name -match 'happ|xray|sing|proxy|vpn|dns|wucs' -or $_.DisplayName -match 'happ|xray|sing|proxy|vpn|dns|wucs' } | Select-Object Name,DisplayName,Status | Format-Table -AutoSize",
        ],
    )
    run_command(
        lines,
        "Happ/xray/sing-box processes",
        [
            POWERSHELL,
            "-NoProfile",
            "-Command",
            "Get-Process | Where-Object { $_.ProcessName -match 'happ|xray|sing|proxy|vpn|amnezia|clash|v2ray|hiddify|outline' } | Select-Object ProcessName,Id,Path | Format-Table -AutoSize",
        ],
    )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    path = write_log()
    print(f"Network probe log: {path}")


if __name__ == "__main__":
    main()
