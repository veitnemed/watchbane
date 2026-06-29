"""Download poster images for watched titles into local cache."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from posters.cache import (
    DEFAULT_POSTER_IMAGES_DIR,
    load_poster_cache,
    poster_identity_key,
    save_poster_cache,
)
from storage import data as storage_data

MAX_POSTER_BYTES = 5 * 1024 * 1024
PREVIEW_POSTER_DIR = DEFAULT_POSTER_IMAGES_DIR / "preview"


def _safe_image_filename(identity: str) -> str:
    safe = identity.replace("|", "_").replace("/", "_").replace("\\", "_")
    return f"{safe}.jpg"


def poster_image_path_for_identity(identity: str) -> Path:
    """Return the default local image path for a poster-cache identity."""
    return DEFAULT_POSTER_IMAGES_DIR / _safe_image_filename(identity)


def _download_poster(url: str, destination: Path) -> bool:
    request = Request(url, headers={"User-Agent": "TerminalMoviesLearn/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            content = response.read(MAX_POSTER_BYTES + 1)
    except (URLError, OSError, ValueError):
        return False

    if len(content) == 0 or len(content) > MAX_POSTER_BYTES:
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return destination.is_file()


def _preview_poster_path(poster_url: str) -> Path:
    digest = hashlib.sha256(poster_url.encode("utf-8")).hexdigest()[:24]
    return PREVIEW_POSTER_DIR / f"{digest}.jpg"


def download_poster_url_for_preview(poster_url: str) -> str | None:
    """Download one poster URL into preview cache for GUI add-title preview."""
    url = str(poster_url or "").strip()
    if url == "" or url.startswith(("http://", "https://")) is False:
        return None

    destination = _preview_poster_path(url)
    if destination.is_file():
        return str(destination)
    if _download_poster(url, destination) is False:
        return None
    return str(destination)


def _ensure_poster_image_downloaded(identity: str, entry: dict) -> str:
    """Download one cache entry when possible. Returns result reason."""
    if isinstance(entry, dict) is False:
        return "skipped_invalid"

    if entry.get("status") != "found":
        return "skipped_not_found"

    poster_url = entry.get("poster_url")
    if poster_url in (None, ""):
        return "skipped_no_url"

    destination = poster_image_path_for_identity(identity)
    if destination.is_file():
        entry["local_path"] = str(destination)
        return "skipped_existing"

    if _download_poster(str(poster_url), destination) is False:
        return "failed"

    entry["local_path"] = str(destination)
    return "downloaded"


def download_poster_for_title(title: str, year, *, cache: dict | None = None) -> dict:
    """Download poster image for one watched title when cache has a URL."""
    identity = poster_identity_key(title, year)
    owns_cache = cache is None
    poster_cache = load_poster_cache() if owns_cache else cache
    entry = poster_cache.get(identity)

    if isinstance(entry, dict) is False:
        return {
            "ok": False,
            "reason": "missing_cache",
            "local_path": None,
            "identity": identity,
        }

    result_reason = _ensure_poster_image_downloaded(identity, entry)
    if owns_cache:
        save_poster_cache(poster_cache)

    ok = result_reason in {"downloaded", "skipped_existing"}
    return {
        "ok": ok,
        "reason": result_reason,
        "local_path": entry.get("local_path"),
        "identity": identity,
    }


def remove_local_poster_file(title: str, year, *, cache_entry: dict | None = None) -> dict:
    """Delete local poster image file for one watched title, if present."""
    identity = poster_identity_key(title, year)
    candidate_paths: list[Path] = []

    if isinstance(cache_entry, dict):
        local_path = cache_entry.get("local_path")
        if local_path not in (None, ""):
            candidate_paths.append(Path(str(local_path)))

    default_path = poster_image_path_for_identity(identity)
    if default_path not in candidate_paths:
        candidate_paths.append(default_path)

    deleted_paths: list[str] = []
    for path in candidate_paths:
        try:
            if path.is_file():
                path.unlink()
                deleted_paths.append(str(path))
        except OSError:
            continue

    return {
        "deleted": len(deleted_paths) > 0,
        "paths": deleted_paths,
        "identity": identity,
    }


def download_poster_images(*, progress_callback=None) -> dict:
    """Download poster_url entries into data/cache/posters/images/."""
    poster_cache = load_poster_cache()
    data = storage_data.load_dataset()

    stats = {
        "total_entries": len(poster_cache),
        "candidates": 0,
        "downloaded": 0,
        "skipped_existing": 0,
        "failed": 0,
    }

    title_by_identity = {}
    for dataset_key, movie in data.items():
        main_info = movie.get("main_info") or {}
        title = str(main_info.get("title") or movie.get("title") or dataset_key).strip()
        year = main_info.get("year", movie.get("year"))
        title_by_identity[poster_identity_key(title, year)] = (title, year)

    processed = 0
    for identity, entry in poster_cache.items():
        processed += 1
        if isinstance(entry, dict) is False:
            continue
        if entry.get("status") != "found":
            continue

        poster_url = entry.get("poster_url")
        if poster_url in (None, ""):
            continue

        stats["candidates"] += 1
        result_reason = _ensure_poster_image_downloaded(identity, entry)
        if result_reason == "skipped_existing":
            stats["skipped_existing"] += 1
        elif result_reason == "downloaded":
            stats["downloaded"] += 1
        elif result_reason == "failed":
            stats["failed"] += 1

        if progress_callback is not None:
            progress_callback(processed, len(poster_cache), entry.get("title") or identity)

    save_poster_cache(poster_cache)
    return stats
