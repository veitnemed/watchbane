from __future__ import annotations

from PyQt6.QtTest import QSignalSpy


def _candidate(index: int, *, poster_url: str | None = None, local_path: str | None = None) -> dict:
    return {
        "pool_entry_key": f"candidate-{index}|2024|movie",
        "title": f"Candidate {index}",
        "year": 2024,
        "media_type": "movie",
        "poster_url": poster_url,
        "local_path": local_path,
    }


def _patch_candidate_posters(monkeypatch) -> None:
    import desktop.candidates.presenters as presenters

    monkeypatch.setattr(
        presenters,
        "resolve_local_poster_path_for_candidate",
        lambda candidate, data_language="ru": candidate.get("local_path"),
    )
    monkeypatch.setattr(
        presenters,
        "candidate_poster_url_for_download",
        lambda candidate, data_language="ru": candidate.get("poster_url"),
    )


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


def test_first_eight_batch_candidates_keep_ranked_queue_priority(qapp, monkeypatch) -> None:
    import desktop.candidates.poster_prefetch as module

    _patch_candidate_posters(monkeypatch)
    monkeypatch.setattr(module, "local_preview_poster_path_if_cached", lambda _url: None)
    controller = module.CandidatePosterPrefetchController(parent=qapp)
    monkeypatch.setattr(controller, "_pump", lambda: None)
    candidates = [
        _candidate(index, poster_url=f"https://example.com/{index}.jpg")
        for index in range(12)
    ]

    controller.start_batch(candidates, data_language="ru", priority_count=8)

    queued = list(controller._queue)
    assert queued[:8] == [f"https://example.com/{index}.jpg" for index in range(8)]
    assert queued[8:] == [f"https://example.com/{index}.jpg" for index in range(8, 12)]


def test_cache_only_batch_reports_progress_and_finishes(qapp, monkeypatch) -> None:
    import desktop.candidates.poster_prefetch as module

    _patch_candidate_posters(monkeypatch)
    controller = module.CandidatePosterPrefetchController(parent=qapp)
    started = QSignalSpy(controller.batch_started)
    progress = QSignalSpy(controller.batch_progress)
    finished = QSignalSpy(controller.batch_finished)
    candidates = [
        _candidate(index, local_path=f"cached-{index}.jpg")
        for index in range(3)
    ]

    batch_id = controller.start_batch(candidates, data_language="ru", priority_count=2)

    assert list(started[-1]) == [batch_id, 3]
    assert list(progress[-1]) == [batch_id, 3, 0, 3, 3, 3]
    assert list(finished[-1]) == [batch_id, 3, 0, 3, 3]


def test_url_cache_hit_is_counted_in_batch_progress(qapp, monkeypatch) -> None:
    import desktop.candidates.poster_prefetch as module

    _patch_candidate_posters(monkeypatch)
    monkeypatch.setattr(
        module,
        "local_preview_poster_path_if_cached",
        lambda _url: "url-cache.jpg",
    )
    controller = module.CandidatePosterPrefetchController(parent=qapp)
    progress = QSignalSpy(controller.batch_progress)
    finished = QSignalSpy(controller.batch_finished)

    batch_id = controller.start_batch(
        [_candidate(1, poster_url="https://example.com/poster.jpg")],
        data_language="ru",
        priority_count=1,
    )

    assert list(progress[-1]) == [batch_id, 1, 0, 1, 1, 1]
    assert list(finished[-1]) == [batch_id, 1, 0, 1, 1]


def test_candidate_without_poster_url_is_settled_with_fallback(qapp, monkeypatch) -> None:
    import desktop.candidates.poster_prefetch as module

    _patch_candidate_posters(monkeypatch)
    controller = module.CandidatePosterPrefetchController(parent=qapp)
    settled = QSignalSpy(controller.candidate_settled)
    progress = QSignalSpy(controller.batch_progress)
    finished = QSignalSpy(controller.batch_finished)
    candidate = _candidate(1)

    batch_id = controller.start_batch([candidate], data_language="ru", priority_count=1)

    assert list(settled[-1]) == [batch_id, "candidate-1|2024|movie", "", False, False]
    assert list(progress[-1]) == [batch_id, 0, 0, 1, 1, 0]
    assert list(finished[-1]) == [batch_id, 0, 0, 1, 0]


def test_failed_request_settles_and_finishes_batch(qapp, monkeypatch) -> None:
    import desktop.candidates.poster_prefetch as module

    _patch_candidate_posters(monkeypatch)
    monkeypatch.setattr(module, "local_preview_poster_path_if_cached", lambda _url: None)
    controller = module.CandidatePosterPrefetchController(parent=qapp)
    monkeypatch.setattr(controller, "_pump", lambda: None)
    progress = QSignalSpy(controller.batch_progress)
    finished = QSignalSpy(controller.batch_finished)
    url = "https://example.com/poster.jpg"

    batch_id = controller.start_batch(
        [_candidate(1, poster_url=url)],
        data_language="ru",
        priority_count=1,
    )
    controller._finish_url(url, None)

    assert list(progress[-1]) == [batch_id, 0, 1, 1, 1, 0]
    assert list(finished[-1]) == [batch_id, 0, 1, 1, 0]
    assert url in controller._attempted_urls
    controller._failed_at[url] -= 31.0
    controller.allow_failed_retries()
    assert url not in controller._attempted_urls


def test_network_host_cooldown_settles_later_posters_without_requests(qapp, monkeypatch) -> None:
    import desktop.candidates.poster_prefetch as module

    _patch_candidate_posters(monkeypatch)
    monkeypatch.setattr(module, "local_preview_poster_path_if_cached", lambda _url: None)
    controller = module.CandidatePosterPrefetchController(parent=qapp)
    monkeypatch.setattr(controller, "_pump", lambda: None)
    failed_url = "https://image.tmdb.org/t/p/w342/one.jpg"
    queued_url = "https://image.tmdb.org/t/p/w342/two.jpg"

    batch_id = controller.start_batch(
        [
            _candidate(1, poster_url=failed_url),
            _candidate(2, poster_url=queued_url),
        ],
        data_language="ru",
        priority_count=2,
    )
    controller._suspend_host(
        failed_url,
        module.QNetworkReply.NetworkError.ConnectionRefusedError,
        "connection refused",
    )
    controller._pump = module.CandidatePosterPrefetchController._pump.__get__(controller)
    controller._pump()

    assert controller._active == {}
    assert controller._queue == module.deque()
    assert controller._batch is not None
    assert controller._batch.batch_id == batch_id
    assert controller._batch.failed == 2
    assert controller._batch.settled == 2


def test_replaced_batch_events_do_not_update_new_generation(qapp, monkeypatch) -> None:
    import desktop.candidates.poster_prefetch as module

    _patch_candidate_posters(monkeypatch)
    monkeypatch.setattr(module, "local_preview_poster_path_if_cached", lambda _url: None)
    controller = module.CandidatePosterPrefetchController(parent=qapp)
    monkeypatch.setattr(controller, "_pump", lambda: None)
    progress = QSignalSpy(controller.batch_progress)
    ready = QSignalSpy(controller.poster_ready)
    old_url = "https://example.com/old.jpg"
    new_url = "https://example.com/new.jpg"

    old_batch_id = controller.start_batch(
        [_candidate(1, poster_url=old_url)],
        data_language="ru",
        priority_count=1,
    )
    controller._network_failed = 3
    new_batch_id = controller.start_batch(
        [_candidate(2, poster_url=new_url)],
        data_language="ru",
        priority_count=1,
    )
    progress_after_replacement = len(progress)
    controller._finish_url(old_url, "old.jpg")

    assert old_batch_id != new_batch_id
    assert controller._network_failed == 0
    assert len(progress) == progress_after_replacement
    assert len(ready) == 0
    assert list(controller._queue) == [new_url]

    controller._finish_url(new_url, "new.jpg")
    assert list(progress[-1]) == [new_batch_id, 1, 0, 1, 1, 0]
    assert list(ready[-1]) == ["candidate-2|2024|movie", "new.jpg"]
