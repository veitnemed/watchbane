"""Scenario runtime reports for debugging GUI/service flows."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPORTS_DIR = ROOT_DIR / "logs" / "reports"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _timestamp_for_file() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _slug(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-zА-Яа-я_-]+", "_", str(value or "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80] or "scenario"


def _duration(started_at: float) -> float:
    return round(time.perf_counter() - started_at, 3)


def summarize_bundle(bundle) -> dict:
    """Return a compact, JSON-safe summary of AddTitleResolveBundle."""
    preview_card = getattr(bundle, "preview_card", {}) or {}
    defaults = getattr(bundle, "defaults", {}) or {}
    meta_payload = getattr(bundle, "meta_payload", {}) or {}
    poster_hints = getattr(bundle, "poster_hints", {}) or {}
    return {
        "found": bool(getattr(bundle, "found", False)),
        "statuses": dict(getattr(bundle, "statuses", {}) or {}),
        "title": str(getattr(bundle, "title", "") or ""),
        "country": str(getattr(bundle, "country", "") or ""),
        "preview_card": {
            "title": preview_card.get("title"),
            "year": preview_card.get("year"),
            "country": preview_card.get("country"),
            "tmdb_score": preview_card.get("tmdb_score"),
            "tmdb_votes": preview_card.get("tmdb_votes"),
            "tmdb_popularity": preview_card.get("tmdb_popularity"),
        },
        "defaults_present": bool(defaults),
        "meta_payload_keys": sorted(meta_payload.keys()) if isinstance(meta_payload, dict) else [],
        "poster_hints_keys": sorted(poster_hints.keys()) if isinstance(poster_hints, dict) else [],
    }


def write_report(report: dict, reports_dir: str | Path = DEFAULT_REPORTS_DIR) -> dict:
    """Write JSON and text report files. Returns paths."""
    output_dir = Path(reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    status = _slug(str(report.get("status") or "unknown"))
    scenario = _slug(str(report.get("scenario") or "scenario"))
    stem = f"{_timestamp_for_file()}_{scenario}_{status}"
    json_path = output_dir / f"{stem}.json"
    txt_path = output_dir / f"{stem}.txt"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_path.write_text(format_text_report(report), encoding="utf-8")
    return {"json_path": str(json_path), "text_path": str(txt_path)}


def format_text_report(report: dict) -> str:
    """Human-readable report body."""
    lines = [
        f"Scenario: {report.get('scenario')}",
        f"Status: {report.get('status')}",
        f"Started: {report.get('started_at')}",
        f"Finished: {report.get('finished_at')}",
        f"Duration: {report.get('duration_seconds')}s",
        "",
        "Inputs:",
        json.dumps(report.get("inputs") or {}, ensure_ascii=False, indent=2),
        "",
    ]

    progress = report.get("progress") or []
    if progress:
        lines.append("Progress:")
        for item in progress:
            lines.append(f"- {item.get('current')}/{item.get('total')} {item.get('message')}")
        lines.append("")

    if report.get("result") is not None:
        lines.append("Result:")
        lines.append(json.dumps(report.get("result"), ensure_ascii=False, indent=2))
        lines.append("")

    if report.get("stdout"):
        lines.append("Stdout:")
        lines.append(str(report.get("stdout")).rstrip())
        lines.append("")

    if report.get("stderr"):
        lines.append("Stderr:")
        lines.append(str(report.get("stderr")).rstrip())
        lines.append("")

    if report.get("error"):
        lines.append("Error:")
        lines.append(str(report.get("error")).rstrip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def run_add_title_report(
    title: str,
    country: str = "Россия",
    *,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    resolver: Callable | None = None,
) -> dict:
    """Run add-title resolve and persist a scenario report."""
    from dataset import service

    resolver = resolver or service.resolve_title_for_add
    progress: list[dict] = []
    started_perf = time.perf_counter()
    report = {
        "scenario": "add-title-resolve",
        "status": "running",
        "started_at": _now_iso(),
        "inputs": {"title": title, "country": country},
        "progress": progress,
    }

    def on_progress(current: int, total: int, message: str) -> None:
        progress.append({"current": current, "total": total, "message": message, "at": _now_iso()})

    try:
        bundle = resolver(title, country, on_progress=on_progress)
        result = summarize_bundle(bundle)
        report["result"] = result
        report["status"] = "ok" if result["found"] else "not_found"
    except Exception as error:  # noqa: BLE001 - diagnostics must capture everything
        report["status"] = "error"
        report["error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }

    report["finished_at"] = _now_iso()
    report["duration_seconds"] = _duration(started_perf)
    report["files"] = write_report(report, reports_dir)
    return report


def run_command_report(
    name: str,
    command: list[str],
    *,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    timeout_seconds: int | None = None,
) -> dict:
    """Run an arbitrary command and persist stdout/stderr/status."""
    started_perf = time.perf_counter()
    report = {
        "scenario": f"command-{name}",
        "status": "running",
        "started_at": _now_iso(),
        "inputs": {"command": command, "timeout_seconds": timeout_seconds},
    }

    try:
        completed = subprocess.run(
            command,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        report["returncode"] = completed.returncode
        report["stdout"] = completed.stdout
        report["stderr"] = completed.stderr
        report["status"] = "ok" if completed.returncode == 0 else "failed"
    except subprocess.TimeoutExpired as error:
        report["status"] = "timeout"
        report["stdout"] = error.stdout or ""
        report["stderr"] = error.stderr or ""
        report["error"] = f"Command timed out after {timeout_seconds}s"
    except Exception as error:  # noqa: BLE001
        report["status"] = "error"
        report["error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }

    report["finished_at"] = _now_iso()
    report["duration_seconds"] = _duration(started_perf)
    report["files"] = write_report(report, reports_dir)
    return report


def print_report_result(report: dict) -> None:
    files = report.get("files") or {}
    print(f"Status: {report.get('status')}")
    print(f"JSON: {files.get('json_path')}")
    print(f"TXT: {files.get('text_path')}")
    if report.get("status") in {"error", "failed", "timeout"}:
        sys.exit(1)
