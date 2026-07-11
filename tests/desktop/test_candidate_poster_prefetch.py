from __future__ import annotations


def test_cached_poster_is_emitted_without_network(qapp, monkeypatch) -> None:
    import desktop.candidates.poster_prefetch as module

    monkeypatch.setattr(
        module,
        "local_preview_poster_path_if_cached",
        lambda url: "cached-poster.jpg" if url.endswith("poster.jpg") else None,
    )
    controller = module.CandidatePosterPrefetchController(parent=qapp)
    ready: list[tuple[str, str]] = []
    controller.poster_ready.connect(lambda identity, path: ready.append((identity, path)))

    controller.enqueue("candidate-1", "https://image.tmdb.org/t/p/original/poster.jpg")

    assert ready == [("candidate-1", "cached-poster.jpg")]
    assert controller._active == {}
    assert list(controller._queue) == []


def test_selected_poster_moves_to_front_of_pending_queue(qapp, monkeypatch) -> None:
    import desktop.candidates.poster_prefetch as module

    monkeypatch.setattr(module, "local_preview_poster_path_if_cached", lambda _url: None)
    controller = module.CandidatePosterPrefetchController(parent=qapp)
    monkeypatch.setattr(controller, "_pump", lambda: None)

    controller.enqueue("candidate-1", "https://example.com/one.jpg")
    controller.enqueue("candidate-2", "https://example.com/two.jpg")
    controller.enqueue("candidate-3", "https://example.com/three.jpg")
    controller.enqueue("candidate-2", "https://example.com/two.jpg", priority=True)

    assert list(controller._queue) == [
        "https://example.com/two.jpg",
        "https://example.com/one.jpg",
        "https://example.com/three.jpg",
    ]
    assert controller._busy is True


def test_failed_batch_reports_completion_and_allows_later_retry(qapp, monkeypatch) -> None:
    import desktop.candidates.poster_prefetch as module

    url = "https://example.com/poster.jpg"
    monkeypatch.setattr(module, "local_preview_poster_path_if_cached", lambda _url: None)
    controller = module.CandidatePosterPrefetchController(parent=qapp)
    completed: list[tuple[int, int]] = []
    controller.batch_finished.connect(lambda succeeded, failed: completed.append((succeeded, failed)))
    controller._busy = True
    controller._waiters[url].add("candidate-1")

    controller._finish_url(url, None)
    controller._update_busy()

    assert completed == [(0, 1)]
    assert url in controller._attempted_urls
    controller._failed_at[url] -= 31.0
    controller.allow_failed_retries()
    assert url not in controller._attempted_urls
