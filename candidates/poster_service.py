"""Candidate-pool poster download use case."""

from __future__ import annotations

from candidates.pool.diagnostics import build_candidate_poster_diagnostics, collect_candidate_poster_download_urls
from candidates.pool_service import get_search_overview_view


def download_candidate_pool_preview_posters(*, progress_callback=None, error_callback=None, result_callback=None, should_stop_callback=None) -> dict:
    """Download pool poster URLs that do not yet have a local preview."""
    from posters.download_images import download_preview_posters_for_urls
    overview = get_search_overview_view()
    if overview.get("is_empty"):
        return {"ok": False, "is_empty_pool": True, "pool_total": 0, "unique_urls": 0, "poster_displayable": 0, "poster_metadata_only": 0, "poster_missing": 0, "download_queue_total": 0, "already_displayable": 0, "downloaded": 0, "skipped_existing": 0, "failed": 0, "skipped_invalid": 0, "failures": []}
    candidates = overview["candidates"]
    counts = build_candidate_poster_diagnostics(candidates).get("counts") or {}
    urls = collect_candidate_poster_download_urls(candidates)
    if not urls:
        stats = {"total_urls": 0, "downloaded": 0, "skipped_existing": 0, "failed": 0, "skipped_invalid": 0, "failures": []}
    else:
        call_kwargs = {"progress_callback": progress_callback, "error_callback": error_callback}
        if result_callback is not None:
            call_kwargs["result_callback"] = result_callback
        if should_stop_callback is not None:
            call_kwargs["should_stop_callback"] = should_stop_callback
        stats = download_preview_posters_for_urls(urls, **call_kwargs)
    return {"ok": True, "is_empty_pool": False, "pool_total": len(candidates), "unique_urls": len(urls), "poster_displayable": int(counts.get("displayable") or 0), "poster_metadata_only": int(counts.get("metadata_only") or 0), "poster_missing": int(counts.get("missing") or 0), "download_queue_total": len(urls), "already_displayable": int(counts.get("displayable") or 0), **stats}
