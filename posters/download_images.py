"""Download poster images for watched titles into local cache."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import shutil
import socket
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.error import HTTPError, URLError
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
PREVIEW_DOWNLOAD_SIZE = "w342"
PREVIEW_BULK_DELAY_SECONDS = 2.0
PREVIEW_BATCH_SIZE = 15
PREVIEW_BATCH_COOLDOWN_SECONDS = 15.0
PREVIEW_DOWNLOAD_MAX_RETRIES = 4
PREVIEW_RETRYABLE_HTTP_CODES = {403, 429, 500, 502, 503, 504}
PREVIEW_FORBIDDEN_BACKOFF_SECONDS = 10.0
PREVIEW_SSL_BACKOFF_SECONDS = 12.0
PREVIEW_CONSECUTIVE_FAILURE_THRESHOLD = 3
PREVIEW_CONSECUTIVE_FAILURE_COOLDOWN_SECONDS = 45.0
TMDB_REFERER = "https://www.themoviedb.org/"
TMDB_IMAGE_HOST = "image.tmdb.org"
TMDB_IMAGE_PROXY = "https://wsrv.nl/"
DEFAULT_POSTER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

TMDB_IMAGE_SIZE_PATTERN = re.compile(
    r"^(https://image\.tmdb\.org/t/p/)([^/]+)(/.*)$",
    re.IGNORECASE,
)


def _safe_image_filename(identity: str) -> str:
    safe = identity.replace("|", "_").replace("/", "_").replace("\\", "_")
    return f"{safe}.jpg"


def poster_image_path_for_identity(identity: str) -> Path:
    """Return the default local image path for a poster-cache identity."""
    return DEFAULT_POSTER_IMAGES_DIR / _safe_image_filename(identity)


def normalize_tmdb_poster_download_url(
    poster_url: str,
    *,
    size: str = PREVIEW_DOWNLOAD_SIZE,
) -> str | None:
    """Prefer a smaller TMDb image size for reliable preview downloads."""
    text = str(poster_url or "").strip()
    if text == "" or text.startswith(("http://", "https://")) is False:
        return None

    match = TMDB_IMAGE_SIZE_PATTERN.match(text)
    if match is None:
        return text

    prefix, _current_size, path = match.groups()
    if path in ("", "/"):
        return None
    return f"{prefix}{size}{path}"


@lru_cache(maxsize=1)
def tmdb_image_delivery_is_loopback() -> bool:
    """Return whether local DNS redirects TMDb image delivery to this machine."""
    try:
        records = socket.getaddrinfo(
            TMDB_IMAGE_HOST,
            443,
            type=socket.SOCK_STREAM,
        )
    except OSError:
        return False

    addresses = []
    for record in records:
        try:
            addresses.append(ipaddress.ip_address(record[4][0]))
        except (IndexError, TypeError, ValueError):
            continue
    return bool(addresses) and all(address.is_loopback for address in addresses)


def poster_download_url_for_network(
    poster_url: str,
    *,
    size: str = PREVIEW_DOWNLOAD_SIZE,
) -> str | None:
    """Return a reachable download URL while keeping the source URL cache-stable."""
    direct_url = normalize_tmdb_poster_download_url(poster_url, size=size)
    if direct_url in (None, ""):
        return None

    parsed = urlsplit(direct_url)
    if parsed.hostname != TMDB_IMAGE_HOST or tmdb_image_delivery_is_loopback() is False:
        return direct_url

    upstream = f"{parsed.netloc}{parsed.path}"
    if parsed.query:
        upstream = f"{upstream}?{parsed.query}"
    return f"{TMDB_IMAGE_PROXY}?{urlencode({'url': upstream, 'output': 'jpg'})}"


def build_poster_request_headers(url: str) -> dict[str, str]:
    """Build HTTP headers that work with TMDb image CDN and generic poster URLs."""
    headers = {
        "User-Agent": DEFAULT_POSTER_USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Connection": "close",
    }
    if "image.tmdb.org" in str(url or "").lower():
        headers["Referer"] = TMDB_REFERER
    return headers


def _format_download_error(error: BaseException) -> str:
    if isinstance(error, HTTPError):
        return f"http_{error.code}"

    reason = getattr(error, "reason", error)
    reason_text = str(reason).lower()
    if "ssl" in reason_text or "unexpected_eof" in reason_text:
        return "network_ssl"
    if "timed out" in reason_text or "timeout" in reason_text:
        return "network_timeout"
    return "network"


def _retry_sleep_seconds(reason: str, attempt: int) -> float:
    if reason in {"http_403", "http_429"}:
        return PREVIEW_FORBIDDEN_BACKOFF_SECONDS * (attempt + 1)
    if reason == "network_ssl":
        return PREVIEW_SSL_BACKOFF_SECONDS * (attempt + 1)
    if reason == "network":
        return PREVIEW_BULK_DELAY_SECONDS * (attempt + 2)
    return PREVIEW_BULK_DELAY_SECONDS * (attempt + 1)


def _read_response_bytes(response, *, max_bytes: int) -> tuple[bytes | None, str | None]:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(65536)
        if chunk == b"":
            break
        total += len(chunk)
        if total > max_bytes:
            return None, "too_large"
        chunks.append(chunk)
    content = b"".join(chunks)
    if len(content) == 0:
        return None, "empty"
    return content, None


def _download_poster_once(
    url: str,
    destination: Path,
    *,
    max_bytes: int = MAX_POSTER_BYTES,
) -> tuple[bool, str]:
    request = Request(url, headers=build_poster_request_headers(url))
    try:
        with urlopen(request, timeout=30) as response:
            content, read_error = _read_response_bytes(response, max_bytes=max_bytes)
    except HTTPError as error:
        return False, _format_download_error(error)
    except (URLError, OSError, ValueError) as error:
        return False, _format_download_error(error)

    if read_error is not None:
        return False, read_error

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.replace(destination)
    except OSError:
        return False, "write_failed"
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass
    if destination.is_file():
        return True, "downloaded"
    return False, "write_failed"


def _download_poster(url: str, destination: Path) -> bool:
    ok, _reason = _download_poster_once(url, destination)
    return ok


def _is_retryable_download_reason(reason: str) -> bool:
    if reason in {"network", "network_ssl", "network_timeout"}:
        return True
    if reason.startswith("http_") is False:
        return False
    try:
        code = int(reason.split("_", 1)[1])
    except (IndexError, TypeError, ValueError):
        return False
    return code in PREVIEW_RETRYABLE_HTTP_CODES


def _download_preview_poster(source_url: str, destination: Path) -> tuple[bool, str]:
    download_url = poster_download_url_for_network(source_url)
    if download_url in (None, ""):
        return False, "invalid_url"

    last_reason = "network"
    for attempt in range(PREVIEW_DOWNLOAD_MAX_RETRIES):
        ok, reason = _download_poster_once(download_url, destination)
        if ok:
            return True, "downloaded"
        last_reason = reason
        if _is_retryable_download_reason(reason) is False:
            break
        if attempt + 1 < PREVIEW_DOWNLOAD_MAX_RETRIES:
            time.sleep(_retry_sleep_seconds(reason, attempt))
    return False, last_reason


def _preview_poster_path(poster_url: str) -> Path:
    digest = hashlib.sha256(poster_url.encode("utf-8")).hexdigest()[:24]
    return PREVIEW_POSTER_DIR / f"{digest}.jpg"


def preview_poster_path_for_url(poster_url: str) -> Path:
    """Return the deterministic preview-cache destination without downloading."""
    return _preview_poster_path(str(poster_url or "").strip())


def local_preview_poster_path_if_cached(poster_url: str) -> str | None:
    """Return preview-cache path when the file already exists. Never downloads."""
    url = str(poster_url or "").strip()
    if url == "" or url.startswith(("http://", "https://")) is False:
        return None
    destination = _preview_poster_path(url)
    return str(destination) if destination.is_file() else None


def download_poster_url_for_preview(poster_url: str) -> str | None:
    """Download one poster URL into preview cache for GUI add-title preview."""
    url = str(poster_url or "").strip()
    if url == "" or url.startswith(("http://", "https://")) is False:
        return None

    destination = _preview_poster_path(url)
    if destination.is_file():
        return str(destination)
    ok, _reason = _download_preview_poster(url, destination)
    if ok is False:
        return None
    return str(destination)


def _copy_poster_file(source: Path, destination: Path) -> bool:
    """Copy one local poster image into watched cache."""
    if source.is_file() is False:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination.is_file()


def _local_poster_source_path(value) -> Path | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text == "" or text.startswith(("http://", "https://")):
        return None
    path = Path(text)
    return path if path.is_file() else None


def _promote_existing_poster_sources(entry: dict, destination: Path) -> str | None:
    """Reuse preview cache or another local file before a network download."""
    poster_url = entry.get("poster_url")
    if poster_url not in (None, ""):
        preview_path = local_preview_poster_path_if_cached(str(poster_url))
        if preview_path is not None and _copy_poster_file(Path(preview_path), destination):
            entry["local_path"] = str(destination)
            return "downloaded"

    poster_path = _local_poster_source_path(entry.get("poster_path"))
    if poster_path is not None and _copy_poster_file(poster_path, destination):
        entry["local_path"] = str(destination)
        return "downloaded"

    return None


def _ensure_poster_image_downloaded(identity: str, entry: dict, *, force: bool = False) -> str:
    """Download one cache entry when possible. Returns result reason."""
    if isinstance(entry, dict) is False:
        return "skipped_invalid"

    if entry.get("status") != "found":
        return "skipped_not_found"

    poster_url = entry.get("poster_url")
    if poster_url in (None, ""):
        return "skipped_no_url"

    destination = poster_image_path_for_identity(identity)
    if force is False and destination.is_file():
        entry["local_path"] = str(destination)
        return "skipped_existing"

    promoted = _promote_existing_poster_sources(entry, destination)
    if promoted is not None:
        return promoted

    ok, _reason = _download_preview_poster(str(poster_url), destination)
    if ok is False:
        return "failed"

    entry["local_path"] = str(destination)
    return "downloaded"


def download_poster_for_title(title: str, year, *, cache: dict | None = None, force: bool = False) -> dict:
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

    result_reason = _ensure_poster_image_downloaded(identity, entry, force=force)
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


def download_preview_posters_for_urls(
    urls: list[str],
    *,
    progress_callback=None,
    error_callback=None,
    result_callback=None,
    should_stop_callback=None,
) -> dict:
    """Download unique poster URLs into preview cache for candidate pool GUI."""
    stats = {
        "total_urls": len(urls),
        "downloaded": 0,
        "skipped_existing": 0,
        "failed": 0,
        "skipped_invalid": 0,
        "failures": [],
        "stopped": False,
    }

    attempted_downloads = 0
    consecutive_failures = 0

    for index, raw_url in enumerate(urls, start=1):
        if should_stop_callback is not None and should_stop_callback() and index > 1:
            stats["stopped"] = True
            break

        url = str(raw_url or "").strip()
        if progress_callback is not None:
            progress_callback(index, len(urls), url)

        if url == "" or url.startswith(("http://", "https://")) is False:
            stats["skipped_invalid"] += 1
            if result_callback is not None:
                result_callback(index, len(urls), url, "skipped_invalid")
            continue

        destination = _preview_poster_path(url)
        if destination.is_file():
            stats["skipped_existing"] += 1
            if result_callback is not None:
                result_callback(index, len(urls), url, "skipped_existing")
            continue

        ok, reason = _download_preview_poster(url, destination)
        if ok:
            stats["downloaded"] += 1
            result_reason = "downloaded"
            attempted_downloads += 1
            consecutive_failures = 0
        else:
            stats["failed"] += 1
            result_reason = reason
            failure = {"url": url, "reason": reason}
            stats["failures"].append(failure)
            if error_callback is not None:
                error_callback(url, reason)
            attempted_downloads += 1
            consecutive_failures += 1
            if consecutive_failures >= PREVIEW_CONSECUTIVE_FAILURE_THRESHOLD:
                time.sleep(PREVIEW_CONSECUTIVE_FAILURE_COOLDOWN_SECONDS)
                consecutive_failures = 0

        if result_callback is not None:
            result_callback(index, len(urls), url, result_reason)

        if attempted_downloads > 0 and attempted_downloads % PREVIEW_BATCH_SIZE == 0:
            time.sleep(PREVIEW_BATCH_COOLDOWN_SECONDS)
        elif index < len(urls):
            time.sleep(PREVIEW_BULK_DELAY_SECONDS)

    return stats
