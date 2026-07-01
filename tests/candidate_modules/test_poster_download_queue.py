from candidates.pool.diagnostics import (
    build_candidate_poster_diagnostics,
    collect_candidate_poster_download_urls,
)


def test_candidate_with_existing_preview_is_not_in_download_queue(monkeypatch) -> None:
    monkeypatch.setattr(
        "posters.download_images.local_preview_poster_path_if_cached",
        lambda url: "cached.jpg" if url.endswith("/cached.jpg") else None,
    )

    candidates = [
        {"title": "Cached", "poster_url": "https://example.com/cached.jpg"},
        {"title": "Needed", "poster_url": "https://example.com/needed.jpg"},
    ]

    assert collect_candidate_poster_download_urls(candidates) == [
        "https://example.com/needed.jpg",
    ]


def test_candidate_without_poster_metadata_is_missing_and_not_in_download_queue(monkeypatch) -> None:
    monkeypatch.setattr(
        "posters.download_images.local_preview_poster_path_if_cached",
        lambda _url: None,
    )

    candidates = [
        {"title": "No poster"},
        {"title": "Needed", "poster_url": "https://example.com/needed.jpg"},
    ]

    diagnostics = build_candidate_poster_diagnostics(candidates)

    assert diagnostics["counts"]["missing"] == 1
    assert collect_candidate_poster_download_urls(candidates) == [
        "https://example.com/needed.jpg",
    ]


def test_download_candidate_pool_preview_posters_skips_downloader_when_queue_is_empty(
    monkeypatch,
) -> None:
    from candidates import service

    monkeypatch.setattr(
        service,
        "get_search_overview_view",
        lambda: {
            "is_empty": False,
            "candidates": [
                {"title": "Cached", "poster_url": "https://example.com/cached.jpg"},
                {"title": "No poster"},
            ],
        },
    )
    monkeypatch.setattr(
        "posters.download_images.local_preview_poster_path_if_cached",
        lambda url: "cached.jpg" if url.endswith("/cached.jpg") else None,
    )

    def fail_download(*_args, **_kwargs):
        raise AssertionError("downloader should not be called for an empty queue")

    monkeypatch.setattr(
        "posters.download_images.download_preview_posters_for_urls",
        fail_download,
    )

    result = service.download_candidate_pool_preview_posters()

    assert result["ok"] is True
    assert result["download_queue_total"] == 0
    assert result["unique_urls"] == 0
    assert result["already_displayable"] == 1
    assert result["poster_missing"] == 1


def test_console_candidate_summary_view_formats_main_menu_line(monkeypatch) -> None:
    from candidates import service

    monkeypatch.setattr(
        service,
        "get_pool_stats_view",
        lambda: {
            "stats": {
                "unique_total": 3,
                "ready_total": 2,
                "incomplete_total": 1,
            }
        },
    )
    monkeypatch.setattr(
        service,
        "get_candidate_poster_diagnostics_view",
        lambda: {
            "counts": {
                "displayable": 1,
                "metadata_only": 1,
                "missing": 1,
            }
        },
    )

    view = service.get_console_candidate_summary_view()

    assert view == {
        "total": 3,
        "complete": 2,
        "incomplete": 1,
        "posters_displayable": 1,
        "posters_to_download": 1,
        "posters_missing_metadata": 1,
        "line": "Candidate pool: 3 | complete: 2 | posters: 1 | need posters: 1",
    }
