"""Read an operator-built TMDb snapshot without importing it into a user profile."""
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import sys

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


@lru_cache(maxsize=1)
def _read(path, identity):
    items = {}
    total = 0
    with path.open("rb") as stream:
        line_no = 0
        while line := stream.readline(MAX_LINE_BYTES + 1):
            line_no += 1
            total += len(line)
            if len(line) > MAX_LINE_BYTES or total > MAX_FILE_BYTES or line_no > MAX_ROWS:
                raise StorySeedSnapshotError("Каталог превышает лимит размера или числа записей.")
            try:
                key, value = _row(json.loads(line))
                if key in items:
                    raise ValueError
            except (ValueError, UnicodeError) as exc:
                raise StorySeedSnapshotError(f"Некорректная или повторная запись каталога, строка {line_no}.") from exc
            items[key] = value
    if not items:
        raise StorySeedSnapshotError("Файл каталога пуст.")
    # The exporter uses atomic replacement. Never cache a file rewritten mid-read.
    if _identity(path) != identity:
        raise StorySeedSnapshotError("Каталог изменился во время чтения. Повторите поиск.")
    return items


def _identity(path):
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


def load_seed_snapshot(path):
    """Return an ID-keyed read-only snapshot; callers must not mutate its rows."""
    path = Path(path).expanduser().resolve()
    try:
        identity = _identity(path)
        if not path.is_file() or identity[2] > MAX_FILE_BYTES:
            raise StorySeedSnapshotError("Не удалось открыть файл каталога или он слишком большой.")
        return _read(path, identity)
    except OSError as exc:
        raise StorySeedSnapshotError("Не удалось открыть файл каталога.") from exc
