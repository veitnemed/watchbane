from email.message import Message
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from apis.tmdb.detached_transport import DetachedTmdbError, DetachedTmdbTransport, _RejectRedirects


@pytest.mark.parametrize("cap", [False, -1, 2.5, "1"])
def test_invalid_caps(cap):
    with pytest.raises(ValueError):
        DetachedTmdbTransport(cap, bearer=lambda: "fixture")


def test_zero_capacity_and_cancellation_precede_credentials_and_transport():
    def unexpected(*args, **kwargs):
        pytest.fail("local refusal must not touch auth or HTTP")

    for cap, cancelled, reason in ((0, False, "budget_exhausted"), (1, True, "cancelled")):
        transport = DetachedTmdbTransport(cap, bearer=unexpected, opener=unexpected, cancelled=lambda: cancelled)
        with pytest.raises(DetachedTmdbError, match=reason):
            transport.get("/discover/movie", {})
        assert transport.attempts == 0
        assert transport.budget_denials == int(cap == 0)


def test_shared_cap_counts_timeout_relaunch_locales_and_both_media():
    calls = []

    def fake_open(request, *, timeout):
        calls.append(request.full_url)
        assert timeout == 12
        if len(calls) == 2:
            raise TimeoutError("fictional debug secret")
        return BytesIO(b"{}")

    transport = DetachedTmdbTransport(5, bearer=lambda: "fixture", opener=fake_open)
    transport.get("/discover/movie", {})
    with pytest.raises(DetachedTmdbError, match="^transport$") as caught:
        transport.get("/movie/7", {"language": "ru-RU"})
    assert caught.value.__context__ is None
    transport.get("/movie/7", {"language": "ru-RU"})
    transport.get("/movie/7", {"language": "en-US"})
    assert transport.get("/discover/tv", {}) == {}
    with pytest.raises(DetachedTmdbError, match="budget_exhausted"):
        transport.get("/tv/7", {"language": "en-US"})
    assert transport.attempts == len(calls) == 5
    assert transport.budget_denials == 1
    assert calls == ["https://api.themoviedb.org/3" + suffix for suffix in (
        "/discover/movie", "/movie/7?language=ru-RU", "/movie/7?language=ru-RU",
        "/movie/7?language=en-US", "/discover/tv",
    )]


@pytest.mark.parametrize(("status", "reason"), [(302, "redirect"), (429, "throttled")])
def test_redirect_and_429_are_not_retried_and_no_body_is_exposed(status, reason):
    calls = []
    body = BytesIO(b"untrusted secret")
    def fake_open(request, *, timeout):
        calls.append(request.full_url)
        raise HTTPError(request.full_url, status, "untrusted details", Message(), body)
    transport = DetachedTmdbTransport(3, bearer=lambda: "fixture", opener=fake_open)
    with pytest.raises(DetachedTmdbError, match=f"^{reason}$") as caught:
        transport.get("/discover/movie", {})
    assert body.closed
    assert caught.value.status == status and caught.value.__context__ is None
    if status == 429:
        with pytest.raises(DetachedTmdbError, match="^throttled$"):
            transport.get("/discover/tv", {})
    assert transport.attempts == len(calls) == 1


def test_production_redirect_handler_never_returns_a_follow_up_request():
    handler = _RejectRedirects()
    request = Request("https://api.themoviedb.org/3/discover/movie")
    for destination in (request.full_url, "https://example.invalid/"):
        assert handler.redirect_request(request, BytesIO(), 302, "", Message(), destination) is None


@pytest.mark.parametrize(("body", "reason"), [(b"{", "invalid_response"), (b"[]", "invalid_response"),
                                               (b" " * (2 * 1024 * 1024 + 1), "response_too_large")],
                         ids=("malformed-json", "non-object-json", "body-over-limit"))
def test_invalid_or_large_response_still_consumes_attempt(body, reason):
    transport = DetachedTmdbTransport(1, bearer=lambda: "fixture", opener=lambda *_a, **_k: BytesIO(body))
    with pytest.raises(DetachedTmdbError, match=f"^{reason}$"):
        transport.get("/tv/7", {})
    assert transport.attempts == 1


def test_invalid_route_and_cancel_during_preparation_consume_nothing():
    stopped = False
    def bearer():
        nonlocal stopped
        stopped = True
        return "fixture"
    transport = DetachedTmdbTransport(1, bearer=bearer, cancelled=lambda: stopped,
                                     opener=lambda *_a, **_k: pytest.fail("unexpected HTTP"))
    with pytest.raises(DetachedTmdbError, match="invalid_route"):
        transport.get("/discover/movie/../../account", {})
    with pytest.raises(DetachedTmdbError, match="invalid_parameter"):
        transport.get("/discover/movie", {"api_key": "fixture"})
    with pytest.raises(DetachedTmdbError, match="cancelled"):
        transport.get("/discover/movie", {})
    assert transport.attempts == transport.budget_denials == 0


def test_actual_opener_pipeline_refuses_redirect_before_second_https_dispatch(monkeypatch):
    from urllib.request import HTTPSHandler
    from urllib.response import addinfourl

    calls = []
    def synthetic_https_open(self, request):
        calls.append(request.full_url)
        headers = Message()
        headers["Location"] = "https://api.themoviedb.org/3/discover/tv"
        response = addinfourl(BytesIO(b"{}"), headers, request.full_url, 302)
        response.msg = "Moved"
        return response

    monkeypatch.setattr(HTTPSHandler, "https_open", synthetic_https_open)
    transport = DetachedTmdbTransport(3, bearer=lambda: "fixture")
    with pytest.raises(DetachedTmdbError, match="^redirect$"):
        transport.get("/discover/movie", {})
    assert calls == ["https://api.themoviedb.org/3/discover/movie"]
    assert transport.attempts == 1


@pytest.mark.parametrize("failure", [OSError, RuntimeError, ValueError])
def test_credential_provider_failures_are_redacted_before_dispatch(failure):
    def unavailable():
        raise failure("fixture credential and provider details")
    transport = DetachedTmdbTransport(1, bearer=unavailable,
                                     opener=lambda *_a, **_k: pytest.fail("unexpected HTTP"))
    with pytest.raises(DetachedTmdbError, match="^invalid_credentials$") as caught:
        transport.get("/discover/movie", {})
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert transport.attempts == transport.budget_denials == 0


def test_invalid_parameter_encoding_is_redacted_before_authentication():
    def unexpected(*_args, **_kwargs):
        pytest.fail("invalid parameters must not touch auth or HTTP")
    transport = DetachedTmdbTransport(1, bearer=unexpected, opener=unexpected)
    with pytest.raises(DetachedTmdbError, match="^invalid_parameter$") as caught:
        transport.get("/discover/movie", {"language": "\ud800"})
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert transport.attempts == transport.budget_denials == 0


@pytest.mark.parametrize(("path", "fault", "missing"), [
    ("/movie/41", None, True), ("/discover/movie", None, False),
    ("/movie/41", "read", False), ("/movie/41", "close", False),
    ("/movie/41", "duplicate", False),
])
def test_missing_error_envelope_never_leaks_or_reclassifies_ambiguous_http(path, fault, missing):
    class ErrorBody(BytesIO):
        def read(self, size=-1):
            if fault == "read":
                raise OSError("private body read failure")
            return super().read(size)
        def close(self):
            super().close()
            if fault == "close":
                raise OSError("private body close failure")
    raw = b'{"success":false,"status_code":34}'
    if fault == "duplicate":
        raw = b'{"success":false,"status_code":6,"status_code":34}'
    def opener(request, **_kwargs):
        raise HTTPError(request.full_url, 404, "private remote message",
                        {"Content-Type": "application/json"}, ErrorBody(raw))
    transport = DetachedTmdbTransport(1, bearer=lambda: "fixture", opener=opener)
    with pytest.raises(DetachedTmdbError, match="^http$") as error:
        transport.get(path, {})
    assert error.value.resource_missing is missing
    assert error.value.status == 404 and error.value.__context__ is None and transport.attempts == 1
