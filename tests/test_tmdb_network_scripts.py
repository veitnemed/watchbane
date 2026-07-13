from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
POWERSHELL = "powershell.exe"


def _run(script: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPTS / script),
            *map(str, args),
        ],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize(
    "script_name",
    [
        "tmdb-network-diagnose.ps1",
        "tmdb-network-compare.ps1",
        "tmdb-dns-recovery.ps1",
        "tmdb-hosts-override.ps1",
    ],
    )
def test_powershell_scripts_pass_windows_parser(script_name: str) -> None:
    script = SCRIPTS / script_name
    escaped_path = str(script).replace("'", "''")
    command = (
        f"$path='{escaped_path}'; $tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile($path,"
        "[ref]$tokens,[ref]$errors) | Out-Null; "
        "if (@($errors).Count) { exit 1 }"
    )
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("payload", "present", "suffix"),
    [
        (None, False, ""),
        ("\ufeff\n  Bearer fake-bearer-token-1234  \n", True, "1234"),
        ("\nraw-token-5678\n", True, "5678"),
        ("TMDB_ACCESS_TOKEN=fake-assignment-token-9012\n", True, "9012"),
    ],
)
def test_token_probe_handles_missing_bom_bearer_and_raw_token(
    tmp_path: Path, payload: str | None, present: bool, suffix: str
) -> None:
    token_path = tmp_path / "token.txt"
    if payload is not None:
        token_path.write_text(payload, encoding="utf-8")
    result = _run(
        "tmdb-network-diagnose.ps1",
        "-TokenProbeOnly",
        "-TokenPath",
        str(token_path),
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip())
    assert report["present"] is present
    assert report["suffix"] == suffix
    assert "fake-bearer-token-1234" not in result.stdout
    assert "raw-token-5678" not in result.stdout
    assert "fake-assignment-token-9012" not in result.stdout


def test_hosts_script_selftest_preserves_unrelated_lines_and_restores_backup(tmp_path: Path) -> None:
    result = _run(
        "tmdb-hosts-override.ps1",
        "-SelfTest",
        "-OutputDirectory",
        str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "SELFTEST OK" in result.stdout
    assert list((tmp_path / "hosts-backups").glob("hosts-*.bak"))


def _host(classes: list[str], *, status: int | None, error: str | None = None) -> dict:
    return {
        "systemDns": {
            "addresses": [
                {"address": f"test-{index}", "classification": value}
                for index, value in enumerate(classes)
            ]
        },
        "trustedDns": [
            {
                "addresses": [
                    {"address": "trusted", "classification": "public-ipv4"}
                ]
            }
        ],
        "https": {"status": status, "error": error, "reached": status is not None},
    }


def _report(
    mode: str,
    *,
    network: bool,
    api_status: int | None,
    poster: bool,
    failure: str,
    api_classes: list[str] | None = None,
) -> dict:
    return {
        "schemaVersion": 1,
        "mode": mode,
        "primaryFailure": failure,
        "networkPathAvailable": network,
        "posterHostAvailable": poster,
        "api": _host(api_classes or ["public-ipv4"], status=api_status, error=failure),
        "poster": _host(["public-ipv4"], status=404 if poster else None, error=None if poster else "timeout"),
    }


@pytest.mark.parametrize(
    ("direct", "vpn", "scenario", "vpn_required"),
    [
        (_report("no-vpn", network=True, api_status=200, poster=True, failure="none", api_classes=["loopback"]), None, "A", False),
        (_report("no-vpn", network=False, api_status=None, poster=False, failure="tcp-timeout"), _report("vpn", network=True, api_status=200, poster=True, failure="none"), "B", True),
        (_report("no-vpn", network=True, api_status=401, poster=True, failure="token-unauthorized"), None, "C", False),
        (_report("no-vpn", network=True, api_status=200, poster=False, failure="poster-host-unavailable"), None, "D", False),
        (_report("no-vpn", network=False, api_status=None, poster=False, failure="tls-failed"), _report("vpn", network=False, api_status=None, poster=False, failure="tls-failed"), "E", False),
    ],
)
def test_vpn_comparison_scenarios(
    tmp_path: Path,
    direct: dict,
    vpn: dict | None,
    scenario: str,
    vpn_required: bool,
) -> None:
    direct_path = tmp_path / "direct.json"
    direct_path.write_text(json.dumps(direct), encoding="utf-8")
    args = ["-NoVpnReport", str(direct_path), "-OutputDirectory", str(tmp_path)]
    if vpn is not None:
        vpn_path = tmp_path / "vpn.json"
        vpn_path.write_text(json.dumps(vpn), encoding="utf-8")
        args += ["-VpnReport", str(vpn_path)]
    result = _run("tmdb-network-compare.ps1", *args)
    assert result.returncode == 0, result.stderr
    comparison_path = max(tmp_path.glob("tmdb-network-comparison-*.json"))
    comparison = json.loads(comparison_path.read_text(encoding="utf-8-sig"))
    assert comparison["scenario"] == scenario
    assert comparison["vpnRequired"] is vpn_required
    assert comparison["hostsOverrideRequired"] is False
