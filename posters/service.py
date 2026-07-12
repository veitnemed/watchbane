"""Public poster resolution and download API."""

from __future__ import annotations

from posters.downloader import download_preview_posters_for_urls
from posters.resolver import resolve_local_poster_path_from_record


def resolve_poster_path(record: dict) -> str | None:
    """Return an existing local poster path without starting network activity."""
    return resolve_local_poster_path_from_record(record)


def queue_poster_downloads(records: list[dict]) -> dict:
    """Collect unique remote poster URLs that lack a local resolved poster."""
    urls: list[str] = []
    seen: set[str] = set()
    for record in records or []:
        if resolve_poster_path(record) is not None:
            continue
        url = str(record.get("poster_url") or "").strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return {"urls": urls, "total": len(urls)}


def download_missing_posters(
    records: list[dict],
    progress_callback=None,
    error_callback=None,
    result_callback=None,
    should_stop_callback=None,
) -> dict:
    """Download poster previews for records missing local poster files."""
    queue = queue_poster_downloads(records)
    if not queue["urls"]:
        return {"total_urls": 0, "downloaded": 0, "skipped_existing": 0, "failed": 0, "skipped_invalid": 0, "failures": []}
    call_kwargs = {"progress_callback": progress_callback, "error_callback": error_callback}
    if result_callback is not None:
        call_kwargs["result_callback"] = result_callback
    if should_stop_callback is not None:
        call_kwargs["should_stop_callback"] = should_stop_callback
    return download_preview_posters_for_urls(queue["urls"], **call_kwargs)
