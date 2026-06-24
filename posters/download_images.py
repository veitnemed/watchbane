"""Download poster images for watched titles into local cache."""

from __future__ import annotations

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


def _safe_image_filename(identity: str) -> str:
    safe = identity.replace("|", "_").replace("/", "_").replace("\\", "_")
    return f"{safe}.jpg"


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
        destination = DEFAULT_POSTER_IMAGES_DIR / _safe_image_filename(identity)
        if destination.is_file():
            entry["local_path"] = str(destination)
            stats["skipped_existing"] += 1
            if progress_callback is not None:
                progress_callback(processed, len(poster_cache), entry.get("title") or identity)
            continue

        if _download_poster(str(poster_url), destination) is False:
            stats["failed"] += 1
            if progress_callback is not None:
                progress_callback(processed, len(poster_cache), entry.get("title") or identity)
            continue

        entry["local_path"] = str(destination)
        stats["downloaded"] += 1
        if progress_callback is not None:
            progress_callback(processed, len(poster_cache), entry.get("title") or identity)

    save_poster_cache(poster_cache)
    return stats
