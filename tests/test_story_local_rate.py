import asyncio
from http.client import HTTPConnection
import json
from threading import Event

import pytest

from web import story_local_rate as local


def test_exact_monotonic_refill_capped_burst_and_numeric_retry():
    tick = [10]
    limiter = local.LocalRateBudget(1, 2, clock=lambda: tick[0])
    assert limiter.retry_after() is None
    assert limiter.retry_after() is None
    assert limiter.retry_after() == 60
    tick[0] += 30_000_000_000
    assert limiter.retry_after() == 30
    tick[0] -= 1  # Broken/injected clock must not mint negative credit.
    assert limiter.retry_after() == 30
    tick[0] += 30_000_000_000
    assert limiter.retry_after() == 1
    tick[0] += 1
    assert limiter.retry_after() is None
    tick[0] += 60_000_000_000_000
    assert [limiter.retry_after() for _ in range(3)] == [None, None, 60]


def test_config_disabled_and_default_burst():
    assert local.local_rate_config(None, None) is None
    assert local.local_rate_config(2, None) == (2, 2)
    assert local.local_rate_config(3600, None) == (3600, 5)


@pytest.mark.parametrize("rate,burst", [(None, 1), (0, None), (3601, None), (True, None),
                                        (60.0, None), (60, False), (60, 0), (60, 61)])
def test_config_refuses_unsafe_or_partial_values(rate, burst):
    with pytest.raises(ValueError, match="Local rate|Local burst"):
        local.local_rate_config(rate, burst)


def tcp_post(port, query):
    conn = HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        body = json.dumps(query, ensure_ascii=False).encode()
        conn.request("POST", "/v1/search", body=body, headers={"Content-Type": "application/json",
                                                              "Watchbane-Search-Outcome": "1"})
        response = conn.getresponse()
        data = json.loads(response.read(2048))
        return response.status, data, response.getheader("Retry-After"), response.getheader("Cache-Control")
    finally:
        conn.close()


@pytest.mark.parametrize("enabled", [False, True], ids=["default-off", "explicit-budget"])
def test_actual_tcp_default_busy_or_rate_limited_then_recovers(enabled, tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    from candidates.story_search import StoryDocument, StoryHit, StoryResponse
    from tools.qa.exercise_story_generation_tcp import listener
    from web.story_api import create_app

    entered, release = Event(), Event()
    calls = []
    tick = [10]
    monkeypatch.setattr(local, "monotonic_ns", lambda: tick[0])
    doc = StoryDocument("tmdb:movie:1", "Синтетический фильм", "Мастер ищет старый архив.", "movie",
                        "fixture", year=2000)

    class BlockingEngine:
        def search(self, query, *, limit):
            if not calls:
                entered.set()
                if not release.wait(timeout=4):
                    raise RuntimeError("fixture admission wait expired")
            calls.append(None)  # deliberately retain no query
            return StoryResponse((StoryHit(doc, 1., doc.overview),))

    options = {"local_rate_per_minute": 60, "local_rate_burst": 2} if enabled else {}
    app = create_app(tmp_path, tmp_path, engine_factory=lambda *_args: BlockingEngine(), **options)
    query = {"query": "мастер ищет архив", "limit": 1}

    async def scenario():
        async with listener(app) as port:
            # The malformed request did not consume either initial token.
            assert (await asyncio.to_thread(tcp_post, port, {}))[0] == 400
            first = asyncio.create_task(asyncio.to_thread(tcp_post, port, query))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                assert await asyncio.to_thread(tcp_post, port, query) == (
                    503, {"detail": "search_busy"}, "1", "no-store")
                third = await asyncio.to_thread(tcp_post, port, query)
                if enabled:
                    assert third == (429, {"detail": "search_rate_limited"}, "1", "no-store")
                else:
                    assert third == (503, {"detail": "search_busy"}, "1", "no-store")
            finally:
                release.set()
            expected = await first
            assert expected[0] == 200 and expected[2:] == (None, "no-store")
            assert expected[1]["results"][0]["id"] == "tmdb:movie:1"
            if enabled:
                # Rate refusal persists even though the one-flight lock is
                # now free. Only monotonic credit recovery clears it.
                assert await asyncio.to_thread(tcp_post, port, query) == (
                    429, {"detail": "search_rate_limited"}, "1", "no-store")
                tick[0] += 1_000_000_000
            assert await asyncio.to_thread(tcp_post, port, query) == expected

    asyncio.run(scenario())
    assert calls == [None, None]


def test_cli_invalid_burst_before_listener_start(monkeypatch):
    uvicorn = pytest.importorskip("uvicorn")
    pytest.importorskip("fastapi")
    from web.story_api import main

    monkeypatch.setattr(uvicorn, "run", lambda *_args, **_kwargs: pytest.fail("opened a listener"))
    with pytest.raises(SystemExit) as error:
        main(["--catalog", "synthetic", "--model-dir", "local", "--local-rate-burst", "2"])
    assert error.value.code == 2
