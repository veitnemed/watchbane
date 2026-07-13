"""Small bounded-retention helpers for local diagnostic files."""

from __future__ import annotations

from pathlib import Path


DEFAULT_MAX_LOG_BYTES = 2 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 3
DEFAULT_DIRECTORY_FILE_LIMIT = 20


def rotate_file(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_LOG_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> bool:
    """Rotate a closed append-only file when it reaches the configured limit."""
    target = Path(path)
    if not target.is_file() or target.stat().st_size < max(1, int(max_bytes)):
        return False
    count = max(1, int(backup_count))
    oldest = Path(f"{target}.{count}")
    oldest.unlink(missing_ok=True)
    for index in range(count - 1, 0, -1):
        source = Path(f"{target}.{index}")
        if source.is_file():
            source.replace(Path(f"{target}.{index + 1}"))
    target.replace(Path(f"{target}.1"))
    return True


def prune_files(
    directory: str | Path,
    pattern: str,
    *,
    keep: int = DEFAULT_DIRECTORY_FILE_LIMIT,
) -> int:
    """Keep only the newest matching files and return the removed count."""
    root = Path(directory)
    if not root.is_dir():
        return 0
    files = sorted(
        (path for path in root.glob(pattern) if path.is_file()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    removed = 0
    for path in files[max(0, int(keep)) :]:
        path.unlink(missing_ok=True)
        removed += 1
    return removed
