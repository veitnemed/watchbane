"""Create a consistent, read-only production SQLite copy for TMDB-1.3a.

This tool never passes the production database to the exporter.  It only reads
the source through SQLite's online backup API and writes a timestamped copy to
an explicitly supplied ignored evidence directory.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.app_paths import DB_FILENAME, get_app_paths


class SnapshotBlocked(RuntimeError):
    """The audit must stop before copying production data."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_profile_name(value: object) -> str:
    name = str(value or "main").strip().casefold()
    return name if re.fullmatch(r"[a-z0-9_-]+", name) else "main"


def production_source() -> tuple[Path, str, Path]:
    """Resolve active-profile DB without importing storage startup modules."""
    environment = {key: value for key, value in os.environ.items() if key != "WATCHBANE_DATA_DIR"}
    paths = get_app_paths(environ=environment)
    active_file = paths.data_dir / "active_profile.json"
    profile = "main"
    try:
        data = json.loads(active_file.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            profile = _safe_profile_name(data.get("active_profile"))
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    data_dir = paths.data_dir if profile == "main" else paths.data_dir / "profiles" / profile
    redacted = f"%LOCALAPPDATA%/Watchbane/data" + ("" if profile == "main" else f"/profiles/{profile}") + f"/{DB_FILENAME}"
    return data_dir / DB_FILENAME, redacted, paths.root


def watchbane_processes() -> list[dict[str, str]]:
    """Return only likely Watchbane processes; do not terminate anything."""
    if os.name != "nt":
        return []
    command = (
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -in "
        "'Watchbane.exe','python.exe','pythonw.exe' } | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=10, check=False)
        raw = json.loads(result.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return []
    rows = raw if isinstance(raw, list) else [raw]
    matches = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("Name") or "")
        line = str(row.get("CommandLine") or "")
        if name.casefold() == "watchbane.exe" or re.search(r"(?:^|[\\/ ])start_app\.py(?:$|[ '\"])", line, re.I):
            matches.append({"pid": str(row.get("ProcessId") or ""), "name": name})
    return matches


def _sidecar_metadata(source: Path) -> dict[str, dict[str, int] | None]:
    result: dict[str, dict[str, int] | None] = {}
    for suffix in ("-wal", "-shm"):
        path = Path(f"{source}{suffix}")
        result[suffix[1:]] = {"size_bytes": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns} if path.is_file() else None
    return result


def fingerprint(source: Path, conn: sqlite3.Connection) -> dict[str, Any]:
    stat = source.stat()
    return {
        "sha256": _sha256(source),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "wal_shm": _sidecar_metadata(source),
        "user_version": int(conn.execute("PRAGMA user_version").fetchone()[0]),
        "page_count": int(conn.execute("PRAGMA page_count").fetchone()[0]),
        "data_version": int(conn.execute("PRAGMA data_version").fetchone()[0]),
    }


def create_snapshot(source: Path, destination_dir: Path) -> tuple[Path, dict[str, Any]]:
    if not source.is_file():
        raise SnapshotBlocked("Production Watchbane database was not found.")
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = destination_dir / f"watchbane-baseline-{stamp}.db"
    if target.exists():
        raise SnapshotBlocked(f"Refusing to overwrite existing snapshot: {target.name}")
    wal_path = Path(f"{source}-wal")
    if wal_path.is_file() and wal_path.stat().st_size > 0:
        raise SnapshotBlocked("Production WAL contains data; close Watchbane and retry after WAL is clean.")
    # ``immutable=1`` prevents a read-only audit connection from creating WAL/
    # SHM sidecars. It is safe only after rejecting a non-empty WAL above.
    source_conn = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    try:
        before = fingerprint(source, source_conn)
        target_conn = sqlite3.connect(target)
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
        after = fingerprint(source, source_conn)
    finally:
        source_conn.close()
    immutable_fields = ("sha256", "size_bytes", "mtime_ns", "wal_shm")
    if any(before[field] != after[field] for field in immutable_fields):
        target.unlink(missing_ok=True)
        raise SnapshotBlocked("Production source changed during snapshot; close Watchbane and retry.")
    report = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source_fingerprint_before": before, "source_fingerprint_after": after, "source_unchanged": True, "snapshot_filename": target.name}
    return target, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    running = watchbane_processes()
    if running:
        parser.error("Watchbane appears to be running. Close it manually before creating a baseline snapshot.")
    source, redacted, _root = production_source()
    try:
        snapshot, report = create_snapshot(source, args.output_dir.resolve())
    except (SnapshotBlocked, OSError, sqlite3.Error) as error:
        parser.error(str(error))
    report["source_database"] = redacted
    (args.output_dir.resolve() / "source_snapshot_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"snapshot": str(snapshot), "source": redacted, "source_unchanged": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
