"""Background poster download jobs for candidate preview posters."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_DIR = ROOT_DIR / "data" / "cache" / "posters" / "jobs"
DEFAULT_JOB_NAME = "candidates"
DEFAULT_LINE_COUNT = 40


@dataclass(frozen=True)
class JobPaths:
    job_name: str
    base_dir: Path
    lock_path: Path
    status_path: Path
    log_path: Path
    stop_path: Path


def _normalize_job_name(job_name: str) -> str:
    normalized = str(job_name or "").strip().lower()
    return normalized if normalized else DEFAULT_JOB_NAME


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _build_job_paths(job_name: str, *, jobs_root: Path | None = None) -> JobPaths:
    normalized = _normalize_job_name(job_name)
    base_dir = (jobs_root or DEFAULT_JOBS_DIR) / normalized
    return JobPaths(
        job_name=normalized,
        base_dir=base_dir,
        lock_path=base_dir / "lock.json",
        status_path=base_dir / "status.json",
        log_path=base_dir / "worker.log",
        stop_path=base_dir / "stop",
    )


def _safe_json_dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def _safe_json_load(path: Path) -> dict:
    if path.is_file() is False:
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_lock_payload(lock_path: Path) -> dict | None:
    return _safe_json_load(lock_path) or None


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        # On Windows and Unix this validates process existence.
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _running_lock_payload(lock_path: Path) -> tuple[bool, int | None]:
    payload = _read_lock_payload(lock_path)
    if not payload:
        return False, None
    raw_pid = payload.get("pid")
    try:
        pid = int(raw_pid)
    except (TypeError, ValueError):
        return False, None
    return _is_pid_alive(pid), pid


def _write_lock(paths: JobPaths, *, pid: int | None, started_at: str | None = None) -> None:
    payload = {
        "pid": pid,
        "started_at": started_at or _utcnow(),
        "job_name": paths.job_name,
    }
    _safe_json_dump(paths.lock_path, payload)


def _acquire_lock(paths: JobPaths, *, pid: int | None) -> bool:
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    if paths.lock_path.exists():
        running, _ = _running_lock_payload(paths.lock_path)
        if running:
            return False
        try:
            paths.lock_path.unlink()
        except OSError:
            pass

    try:
        with open(paths.lock_path, "x", encoding="utf-8") as file:
            payload = {
                "pid": pid,
                "job_name": paths.job_name,
                "started_at": _utcnow(),
            }
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return True
    except FileExistsError:
        return False


def _release_lock(paths: JobPaths) -> None:
    try:
        paths.lock_path.unlink()
    except OSError:
        pass


def _ensure_stop_file_absent(paths: JobPaths) -> None:
    try:
        paths.stop_path.unlink()
    except OSError:
        pass


def _read_existing_status(paths: JobPaths) -> dict:
    status = _safe_json_load(paths.status_path)
    if status:
        return status

    return {
        "job_name": paths.job_name,
        "status": "idle",
        "pid": None,
        "started_at": None,
        "ended_at": None,
        "updated_at": _utcnow(),
        "total_urls": 0,
        "processed_urls": 0,
        "downloaded": 0,
        "skipped_existing": 0,
        "failed": 0,
        "skipped_invalid": 0,
        "last_url": None,
        "failures": [],
        "errors": [],
        "stopped": False,
        "stop_requested": False,
        "is_running": False,
        "is_empty_pool": None,
        "pool_total": None,
        "download_queue_total": None,
    }


def _write_status(paths: JobPaths, status: dict) -> None:
    status["updated_at"] = _utcnow()
    _safe_json_dump(paths.status_path, status)


def _resolve_state(paths: JobPaths) -> dict:
    status = _read_existing_status(paths)
    running, running_pid = _running_lock_payload(paths.lock_path)
    status["is_running"] = running
    status["lock_pid"] = running_pid
    if running:
        status["status"] = status.get("status", "running") or "running"
    elif status.get("status") == "running":
        status["status"] = "stale_lock"

    return status


def get_status(job_name: str = DEFAULT_JOB_NAME) -> dict:
    paths = _build_job_paths(job_name)
    return _resolve_state(paths)


def get_job_paths(job_name: str = DEFAULT_JOB_NAME, *, jobs_root: Path | None = None) -> JobPaths:
    return _build_job_paths(job_name, jobs_root=jobs_root)


def _format_tail_lines(path: Path, lines: int) -> str:
    if lines <= 0:
        return ""
    if path.is_file() is False:
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    all_lines = text.splitlines()
    return "\n".join(all_lines[-lines:])


def start_job(job_name: str = DEFAULT_JOB_NAME) -> dict:
    """Start a candidate poster job in a background process."""
    paths = _build_job_paths(job_name)
    normalized = _normalize_job_name(job_name)

    if normalized != DEFAULT_JOB_NAME:
        return {
            "ok": False,
            "error": f"Unsupported job: {normalized}",
            "status": "unsupported",
        }

    running, running_pid = _running_lock_payload(paths.lock_path)
    if running:
        return {
            "ok": False,
            "already_running": True,
            "status": "running",
            "pid": running_pid,
            "message": f"{normalized} job is already running.",
        }

    if paths.lock_path.exists():
        try:
            paths.lock_path.unlink()
        except OSError:
            pass

    if not _acquire_lock(paths, pid=os.getpid()):
        return {"ok": False, "already_running": True, "status": "running"}

    _ensure_stop_file_absent(paths)

    status = _read_existing_status(paths)
    status["status"] = "starting"
    status["pid"] = os.getpid()
    status["started_at"] = _utcnow()
    status["ended_at"] = None
    status["stop_requested"] = False
    _write_status(paths, status)

    script_path = ROOT_DIR / "scripts" / "poster_download_job.py"
    if script_path.is_file() is False:
        _release_lock(paths)
        return {"ok": False, "error": "CLI script is missing", "status": "failed"}

    command = [sys.executable, "-u", str(script_path), "_run", normalized]
    try:
        with open(paths.log_path, "a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(ROOT_DIR),
                text=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        _write_lock(paths, pid=process.pid, started_at=status.get("started_at"))
        status = _resolve_state(paths)
        status["status"] = "running"
        status["started_at"] = _utcnow() if status.get("started_at") is None else status.get("started_at")
        _write_status(paths, status)
        return {
            "ok": True,
            "status": "running",
            "pid": process.pid,
            "job_name": normalized,
            "log_path": str(paths.log_path),
        }
    except OSError as error:
        _release_lock(paths)
        status["status"] = "failed"
        status["ended_at"] = _utcnow()
        status["error"] = str(error)
        _write_status(paths, status)
        return {"ok": False, "error": str(error), "status": "failed"}


def stop_job(job_name: str = DEFAULT_JOB_NAME) -> dict:
    paths = _build_job_paths(job_name)
    status = _resolve_state(paths)
    running, running_pid = _running_lock_payload(paths.lock_path)
    if not running:
        return {
            "ok": False,
            "status": status.get("status", "idle"),
            "is_running": False,
            "message": f"{paths.job_name} job is not running.",
        }

    _ensure_stop_file_absent(paths)
    paths.stop_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        paths.stop_path.write_text(_utcnow(), encoding="utf-8")
    except OSError:
        return {"ok": False, "error": "Failed to create stop file."}

    status["stop_requested"] = True
    status["pid"] = running_pid
    status["status"] = "stopping"
    _write_status(paths, status)
    return {
        "ok": True,
        "status": "stopping",
        "pid": running_pid,
        "is_running": True,
        "message": f"Stop requested for {paths.job_name} job.",
    }


def _run_candidates_job_for_output(paths: JobPaths) -> dict:
    from candidates import service as candidate_service

    status = _read_existing_status(paths)
    status["status"] = status.get("status", "running") or "running"
    status["started_at"] = status.get("started_at") or _utcnow()
    status["ended_at"] = None
    status["stop_requested"] = False
    status["stopped"] = False
    status["failures"] = []
    status["errors"] = []
    _write_status(paths, status)

    def should_stop() -> bool:
        return paths.stop_path.is_file()

    def on_progress(current: int, total: int, url: str) -> None:
        status["status"] = "running"
        status["total_urls"] = total
        status["processed_urls"] = current
        status["last_url"] = url
        _write_status(paths, status)

    def on_error(url: str, reason: str) -> None:
        status["failed"] = status.get("failed", 0) + 1
        failure = {"url": url, "reason": reason}
        failures = list(status.get("failures") or [])
        failures.append(failure)
        status["failures"] = failures[-50:]
        _write_status(paths, status)

    try:
        results = candidate_service.download_candidate_pool_preview_posters(
            progress_callback=on_progress,
            error_callback=on_error,
            should_stop_callback=should_stop,
        )
    except Exception as error:
        status["status"] = "failed"
        status["ended_at"] = _utcnow()
        status["error"] = str(error)
        _write_status(paths, status)
        return {"ok": False, "status": "failed", "error": str(error)}

    status["status"] = (
        "stopped" if bool(results.get("stopped")) else "finished"
    )
    status["ended_at"] = _utcnow()
    status["pid"] = os.getpid()
    status["pool_total"] = int(results.get("pool_total") or results.get("total", 0))
    status["download_queue_total"] = int(results.get("download_queue_total") or results.get("total_urls") or 0)
    status["total_urls"] = int(results.get("total_urls") or 0)
    status["downloaded"] = int(results.get("downloaded") or 0)
    status["skipped_existing"] = int(results.get("skipped_existing") or 0)
    status["failed"] = int(results.get("failed") or 0)
    status["skipped_invalid"] = int(results.get("skipped_invalid") or 0)
    status["is_empty_pool"] = bool(results.get("is_empty_pool"))
    status["stopped"] = bool(results.get("stopped"))
    status["stop_requested"] = paths.stop_path.is_file()
    status["failures"] = list(results.get("failures") or status.get("failures") or [])
    status["errors"] = list(results.get("errors") or status.get("errors") or [])
    _write_status(paths, status)
    return {"ok": True, "status": status["status"], "state": status}


def run_job(job_name: str = DEFAULT_JOB_NAME) -> int:
    normalized = _normalize_job_name(job_name)
    paths = _build_job_paths(normalized)
    if normalized != DEFAULT_JOB_NAME:
        print(f"Unsupported job: {normalized}")
        return 2
    _ensure_stop_file_absent(paths)

    if paths.base_dir.exists() is False:
        paths.base_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting job: {normalized}")

    result = _run_candidates_job_for_output(paths)

    if paths.stop_path.is_file():
        try:
            paths.stop_path.unlink()
        except OSError:
            pass
    _release_lock(paths)

    final_status = get_status(normalized)
    print(f"Job finished: {final_status.get('status')}")
    print(f"Downloaded: {final_status.get('downloaded', 0)}")
    print(f"Skipped existing: {final_status.get('skipped_existing', 0)}")
    print(f"Failed: {final_status.get('failed', 0)}")
    if final_status.get("stopped"):
        print("Stop requested.")
    return 0 if result.get("ok") else 1


def run_cli(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Background poster download jobs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Start background preview download.")
    start_parser.add_argument("job", nargs="?", default=DEFAULT_JOB_NAME, help="Job name.")

    status_parser = subparsers.add_parser("status", help="Show current job status.")
    status_parser.add_argument("job", nargs="?", default=DEFAULT_JOB_NAME, help="Job name.")

    tail_parser = subparsers.add_parser("tail", help="Show worker log tail.")
    tail_parser.add_argument("job", nargs="?", default=DEFAULT_JOB_NAME, help="Job name.")
    tail_parser.add_argument("--lines", type=int, default=DEFAULT_LINE_COUNT, help="How many lines to show.")

    run_parser = subparsers.add_parser("_run", add_help=False)
    run_parser.add_argument("job", nargs="?", default=DEFAULT_JOB_NAME)

    stop_parser = subparsers.add_parser("stop", help="Request graceful stop.")
    stop_parser.add_argument("job", nargs="?", default=DEFAULT_JOB_NAME, help="Job name.")

    args = parser.parse_args(args=args)

    if args.command == "_run":
        return run_job(args.job)
    if args.command == "start":
        result = start_job(args.job)
        if result.get("ok"):
            print(f"Started job '{result.get('job_name')}' with pid={result.get('pid')}.")
            print(f"Log: {result.get('log_path')}")
            return 0
        print(f"Could not start job: {result.get('message', result.get('error'))}")
        return 1

    if args.command == "status":
        status = get_status(args.job)
        print(f"Job: {status.get('job_name')}")
        print(f"Status: {status.get('status')}")
        print(f"Running: {'yes' if status.get('is_running') else 'no'}")
        print(
            f"Progress: {status.get('processed_urls', 0)}/{status.get('total_urls', 0)}"
        )
        print(
            f"Downloaded: {status.get('downloaded', 0)} | "
            f"skipped_existing: {status.get('skipped_existing', 0)} | "
            f"failed: {status.get('failed', 0)} | "
            f"skipped_invalid: {status.get('skipped_invalid', 0)}"
        )
        if status.get("stop_requested"):
            print("Stop requested: yes")
        if status.get("failures"):
            print(f"Last errors: {len(status['failures'])}")
        if status.get("is_empty_pool") is True:
            print("Candidate pool is empty or has no downloadable URLs.")
        if status.get("error"):
            print(f"Error: {status.get('error')}")
        return 0

    if args.command == "tail":
        paths = _build_job_paths(args.job)
        print(_format_tail_lines(paths.log_path, lines=args.lines))
        return 0

    if args.command == "stop":
        result = stop_job(args.job)
        if result.get("ok"):
            print("Stop request recorded.")
            return 0
        print(result.get("message") or "No running job.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
