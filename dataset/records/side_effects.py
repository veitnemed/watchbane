"""Best-effort side effects after watched record add."""


def run_after_add_side_effects(
    *,
    title: str,
    year,
    movie: dict,
    meta_obj: dict | None,
    pool_candidate=None,
    poster_hints=None,
) -> list[dict]:
    """Return structured side-effect events without printing or calling candidates."""
    events: list[dict] = []

    try:
        from posters.cache import sync_poster_cache_from_meta_and_sources
        from storage.data import get_meta_obj

        extra_sources = poster_hints if isinstance(poster_hints, dict) else None
        if isinstance(pool_candidate, dict):
            from dataset.title_resolve import build_poster_hints_from_candidate

            if build_poster_hints_from_candidate(pool_candidate).get("status") == "found":
                extra_sources = pool_candidate
        sync_poster_cache_from_meta_and_sources(
            title,
            year,
            meta_obj=get_meta_obj(title),
            movie=movie,
            extra_sources=extra_sources,
        )
        events.append({"type": "poster_cache_sync", "ok": True})
    except Exception as error:
        events.append(
            {
                "type": "poster_cache_sync",
                "ok": False,
                "error": str(error),
                "message": f"не удалось обновить poster-cache: {error}",
            }
        )

    try:
        from posters.download_images import download_poster_for_title

        poster_download = download_poster_for_title(title, year)
        if (
            poster_download.get("ok") is False
            and poster_download.get("reason") == "missing_cache"
            and isinstance(poster_hints, dict)
            and poster_hints.get("status") == "found"
            and poster_hints.get("poster_url") not in (None, "")
        ):
            from posters.cache import upsert_poster_cache_entry

            upsert_poster_cache_entry(title, year, poster_hints)
            download_poster_for_title(title, year)
        events.append({"type": "poster_download", "ok": True})
    except Exception as error:
        events.append(
            {
                "type": "poster_download",
                "ok": False,
                "error": str(error),
                "message": f"не удалось скачать постер: {error}",
            }
        )

    if isinstance(pool_candidate, dict):
        events.append(
            {
                "type": "candidate_pool_cleanup",
                "ok": True,
                "candidate": dict(pool_candidate),
            }
        )
    else:
        events.append({"type": "candidate_pool_refresh", "ok": True})

    return events


def apply_add_record_side_effects(side_effects: list[dict] | None, *, print_warnings: bool = True) -> None:
    """Apply deferred side effects from a successful add."""
    for event in side_effects or []:
        if event.get("ok") is False and print_warnings and event.get("message"):
            print(f"Предупреждение: {event['message']}")

        event_type = event.get("type")
        if event_type == "candidate_pool_cleanup":
            try:
                from candidates import service as candidate_service

                candidate = event.get("candidate")
                if isinstance(candidate, dict):
                    candidate_service.mark_candidate_watched_in_pool(candidate)
            except Exception as error:
                if print_warnings:
                    print(f"Предупреждение: не удалось обновить candidate pool после добавления записи: {error}")
        elif event_type == "candidate_pool_refresh":
            try:
                from candidates.repositories import pool_repository

                pool_repository.save_candidate_pool(pool_repository.load_candidate_pool())
            except Exception as error:
                if print_warnings:
                    print(f"Предупреждение: не удалось обновить candidate pool после добавления записи: {error}")
