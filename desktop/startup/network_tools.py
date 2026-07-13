"""Read-only diagnostics and explicitly launched TMDb recovery tools."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from config.app_paths import get_app_paths
from desktop.i18n import tr
from desktop.theme.scaling import scale_px


def tmdb_script_path(name: str) -> Path:
    """Resolve a bundled or source-tree TMDb PowerShell tool."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parents[2]
    return base / "scripts" / name


def diagnostic_output_dir() -> Path:
    """Use a writable per-user directory for packaged diagnostic reports."""
    if getattr(sys, "frozen", False):
        return get_app_paths().root / "diagnostics"
    return Path(__file__).resolve().parents[2] / ".local" / "diagnostics"


def _latest_report(output_dir: Path, *, newer_than: float) -> Path | None:
    candidates = [
        path
        for path in output_dir.glob("tmdb-network-unlabelled-app-token-gate-*.json")
        if path.stat().st_mtime >= newer_than - 2.0
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def run_readonly_tmdb_diagnostics() -> dict[str, Any]:
    """Run the PowerShell diagnostic without changing DNS, hosts or VPN."""
    script = tmdb_script_path("tmdb-network-diagnose.ps1")
    output_dir = diagnostic_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-Label",
        "app-token-gate",
        "-OutputDirectory",
        str(output_dir),
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            command,
            cwd=Path(sys.executable).parent if getattr(sys, "frozen", False) else script.parents[1],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            creationflags=creationflags,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"ok": False, "error": "diagnostic-launch-failed", "details": str(error)}

    report_path = _latest_report(output_dir, newer_than=started)
    if report_path is None:
        return {
            "ok": False,
            "error": "diagnostic-report-missing",
            "exit_code": completed.returncode,
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return {"ok": False, "error": "diagnostic-report-invalid", "details": str(error)}
    report["ok"] = True
    report["report_path"] = str(report_path)
    report["exit_code"] = completed.returncode
    return report


def _address_classes(host_report: dict[str, Any]) -> set[str]:
    dns = host_report.get("systemDns") if isinstance(host_report, dict) else {}
    addresses = dns.get("addresses") if isinstance(dns, dict) else []
    return {
        str(item.get("classification") or "")
        for item in addresses or []
        if isinstance(item, dict)
    }


def _first_address(host_report: dict[str, Any]) -> str:
    dns = host_report.get("systemDns") if isinstance(host_report, dict) else {}
    addresses = dns.get("addresses") if isinstance(dns, dict) else []
    for item in addresses or []:
        if isinstance(item, dict) and item.get("address"):
            return str(item["address"])
    return ""


def format_tmdb_diagnostic_summary(report: dict[str, Any]) -> tuple[str, str]:
    """Return (message, severity) without exposing credentials or local paths."""
    if report.get("ok") is not True:
        return tr("startup.tmdb.diagnostics.failed"), "error"

    api = report.get("api") if isinstance(report.get("api"), dict) else {}
    poster = report.get("poster") if isinstance(report.get("poster"), dict) else {}
    api_classes = _address_classes(api)
    poster_classes = _address_classes(poster)
    api_status = (api.get("https") or {}).get("status") if isinstance(api.get("https"), dict) else None

    if "loopback" in api_classes or "unspecified" in api_classes:
        address = _first_address(api) or "loopback"
        return tr("startup.tmdb.diagnostics.api_loopback").format(address=address), "error"
    if api_status == 401:
        return tr("startup.tmdb.diagnostics.token_unauthorized"), "warning"
    if report.get("networkPathAvailable") is not True:
        failure = str(report.get("primaryFailure") or "network-unavailable")
        return tr("startup.tmdb.diagnostics.network_failure").format(reason=failure), "error"
    if "loopback" in poster_classes or "unspecified" in poster_classes:
        address = _first_address(poster) or "loopback"
        return tr("startup.tmdb.diagnostics.poster_loopback").format(address=address), "warning"
    if report.get("posterHostAvailable") is not True:
        return tr("startup.tmdb.diagnostics.poster_unavailable"), "warning"
    if report.get("apiAuthorized") is True:
        return tr("startup.tmdb.diagnostics.ok"), "success"
    return tr("startup.tmdb.diagnostics.network_ok"), "success"


class TmdbDiagnosticsWorker(QThread):
    """Run PowerShell diagnostics without blocking the token gate."""

    completed = pyqtSignal(dict)

    def run(self) -> None:
        if self.isInterruptionRequested():
            return
        result = run_readonly_tmdb_diagnostics()
        if not self.isInterruptionRequested():
            self.completed.emit(result)


def _launch_powershell(script_name: str, action: str, *, elevated: bool) -> bool:
    script = tmdb_script_path(script_name)
    if not script.is_file():
        return False
    arguments = [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-NoExit",
        "-File",
        str(script),
    ]
    if action:
        arguments.append(action)
    arguments.extend(("-OutputDirectory", str(diagnostic_output_dir())))
    try:
        if elevated:
            import ctypes

            parameters = subprocess.list2cmdline(arguments)
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                "powershell.exe",
                parameters,
                str(script.parents[1]),
                1,
            )
            return int(result) > 32
        subprocess.Popen(
            ["powershell.exe", *arguments],
            cwd=script.parents[1],
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        return True
    except OSError:
        return False


class TmdbRecoveryToolsDialog(QDialog):
    """Launch explicit recovery tools; never modifies the system itself."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("startup.tmdb.tools.title"))
        self.setModal(True)
        self.setMinimumWidth(scale_px(520))
        layout = QVBoxLayout(self)
        explanation = QLabel(tr("startup.tmdb.tools.explanation"))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        actions = (
            ("startup.tmdb.tools.no_vpn", "tmdb-network-diagnose.ps1", "-NoVpn", False),
            ("startup.tmdb.tools.vpn", "tmdb-network-diagnose.ps1", "-Vpn", False),
            ("startup.tmdb.tools.compare", "tmdb-network-compare.ps1", "", False),
            ("startup.tmdb.tools.dns_status", "tmdb-dns-recovery.ps1", "-Status", False),
            ("startup.tmdb.tools.dns_apply", "tmdb-dns-recovery.ps1", "-Apply", True),
            ("startup.tmdb.tools.dns_restore", "tmdb-dns-recovery.ps1", "-Restore", True),
            ("startup.tmdb.tools.hosts_preview", "tmdb-hosts-override.ps1", "-Preview", False),
            ("startup.tmdb.tools.hosts_remove", "tmdb-hosts-override.ps1", "-Remove", True),
            ("startup.tmdb.tools.hosts_restore", "tmdb-hosts-override.ps1", "-Restore", True),
        )
        for text_key, script_name, action, elevated in actions:
            button = QPushButton(tr(text_key), self)
            button.clicked.connect(
                lambda _checked=False, name=script_name, arg=action, admin=elevated: self._launch(
                    name, arg, elevated=admin
                )
            )
            layout.addWidget(button)

        close_button = QPushButton(tr("startup.tmdb.tools.close"), self)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    def _launch(self, script_name: str, action: str, *, elevated: bool) -> None:
        if not _launch_powershell(script_name, action, elevated=elevated):
            QLabel(tr("startup.tmdb.tools.launch_failed"), self).show()
