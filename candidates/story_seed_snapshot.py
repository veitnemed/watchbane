"""Read an operator-built TMDb snapshot without importing it into a user profile."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from threading import Lock

MAX_ROWS = 20_000
MAX_LINE_BYTES = 32 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
_POSTER = re.compile(r"/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)", re.I)


CATALOG_ENV = "WATCHBANE_STORY_SEED_CATALOG"
PUBLISHER_CATALOG = Path("assets") / "story-catalog.jsonl"


def resolve_catalog(launcher_file, explicit_path=None, environment_path=None):
    """Select a local override or optional sidecar next to the actual launcher."""
    if explicit_path is not None:
        return Path(explicit_path).expanduser().resolve()
    if environment_path and environment_path.strip():
        return Path(environment_path).expanduser().resolve()
    # Do not inspect PyInstaller's temporary unpack directory for a publisher
    # asset installed alongside the executable.
    executable = sys.executable if getattr(sys, "frozen", False) else launcher_file
    sidecar = Path(executable).resolve().parent / PUBLISHER_CATALOG
    return sidecar.resolve() if sidecar.exists() or sidecar.is_symlink() else None


def configure_catalog(path):
    """Make launch selection visible to the existing desktop view."""
    if path is None:
        os.environ.pop(CATALOG_ENV, None)
    else:
        os.environ[CATALOG_ENV] = str(path)


class StorySeedSnapshotError(ValueError):
    pass


def _row(raw):
    if not isinstance(raw, dict):
        raise ValueError
    kind, identifier = raw.get("media_type"), raw.get("tmdb_id")
    title, overview = raw.get("title"), raw.get("overview")
    language, year = raw.get("language"), raw.get("year")
    if (kind not in ("movie", "tv") or type(identifier) is not int or identifier <= 0
            or language not in ("ru-RU", "en-US")
            or not isinstance(title, str) or not title.strip() or len(title) > 512
            or not isinstance(overview, str) or not overview.strip() or len(overview) > 8192
            or (year is not None and (type(year) is not int or not 1800 <= year <= 2200))):
        raise ValueError
    key = f"tmdb:{kind}:{identifier}"
    poster = raw.get("poster_path")
    value = dict(title=title.strip(), overview=overview.strip(), media_type=kind,
                 tmdb_id=identifier, year=year, source="TMDb", source_provider="tmdb",
                 localized={language[:2]: {"title": title.strip(), "overview": overview.strip()}})
    if isinstance(poster, str) and _POSTER.fullmatch(poster):
        value["poster_path"] = poster
        value["poster_url"] = "https://image.tmdb.org/t/p/w342" + poster
    return key, value


_cache_lock = Lock()
_cached_snapshot = None


def _read(stream, identity, expected_digest):
    items = {}
    total = 0
    digest = hashlib.sha256()
    stream.seek(0)
    _check_file_identity(stream, identity)
    line_no = 0
    while line := stream.readline(MAX_LINE_BYTES + 1):
        line_no += 1
        total += len(line)
        if len(line) > MAX_LINE_BYTES or total > MAX_FILE_BYTES or line_no > MAX_ROWS:
            raise StorySeedSnapshotError("Каталог превышает лимит размера или числа записей.")
        digest.update(line)
        try:
            key, value = _row(json.loads(line))
            if key in items:
                raise ValueError
        except (ValueError, UnicodeError) as exc:
            raise StorySeedSnapshotError(f"Некорректная или повторная запись каталога, строка {line_no}.") from exc
        items[key] = value
    _check_file_identity(stream, identity)
    if digest.digest() != expected_digest:
        raise StorySeedSnapshotError("Каталог изменился во время чтения. Повторите поиск.")
    if not items:
        raise StorySeedSnapshotError("Файл каталога пуст.")
    return items


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _check_file_identity(stream, identity):
    if _identity(os.fstat(stream.fileno())) != identity:
        raise StorySeedSnapshotError("Каталог изменился во время чтения. Повторите поиск.")


def _snapshot_digest(stream, identity):
    # mtime can be preserved during an in-place copy. A digest prevents stale
    # IDs across platforms even when the remaining metadata is also unchanged.
    digest = hashlib.sha256()
    total = 0
    _check_file_identity(stream, identity)
    while block := stream.read(1024 * 1024):
        total += len(block)
        if total > MAX_FILE_BYTES:
            raise StorySeedSnapshotError("Каталог превышает лимит размера или числа записей.")
        digest.update(block)
    _check_file_identity(stream, identity)
    return digest.digest()


def load_seed_snapshot(path):
    """Return an ID-keyed read-only snapshot; callers must not mutate its rows."""
    return load_seed_snapshot_with_digest(path)[0]


def load_seed_snapshot_with_digest(path):
    """Return snapshot and SHA-256 hex digest of its validated descriptor bytes."""
    global _cached_snapshot
    path = Path(path).expanduser().resolve()
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
            raise StorySeedSnapshotError("Не удалось открыть файл каталога или он слишком большой.")
        path_identity = _identity(info)
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_size > MAX_FILE_BYTES:
                raise StorySeedSnapshotError("Не удалось открыть файл каталога или он слишком большой.")
            # Windows path stat and descriptor fstat can represent the same
            # file with different device/inode metadata. Keep each comparison
            # in its own domain; only the original descriptor supplies bytes.
            identity = _identity(opened)
            if _identity(path.stat()) != path_identity:
                raise StorySeedSnapshotError("Каталог изменился во время чтения. Повторите поиск.")
            digest = _snapshot_digest(stream, identity)
            key = (path, path_identity, digest)
            with _cache_lock:
                cached = _cached_snapshot
            if cached is not None and cached[0] == key:
                result = cached[1]
            else:
                # On miss, parse the same open descriptor, not a new file
                # at this path. Validate bytes again without buffering 64 MiB.
                result = _read(stream, identity, digest)
            if _identity(path.stat()) != path_identity:
                raise StorySeedSnapshotError("Каталог изменился во время чтения. Повторите поиск.")
        with _cache_lock:
            _cached_snapshot = (key, result)
        return result, digest.hex()
    except OSError as exc:
        raise StorySeedSnapshotError("Не удалось открыть файл каталога.") from exc
