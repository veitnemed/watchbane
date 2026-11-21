"""Opt-in, run-scoped TMDb attempt boundary; independent of interactive client."""
from collections.abc import Callable, Mapping
from http.client import HTTPException
import json
import re
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

_ORIGIN = "https://api.themoviedb.org/3"
_ROUTE = re.compile(r"/(?:discover/(?:movie|tv)|(?:movie|tv)/[1-9][0-9]*)")
_BODY_LIMIT = 2 * 1024 * 1024
_TIMEOUT_SECONDS = 12


class DetachedTmdbError(RuntimeError):
    """Fixed, non-secret diagnostic; callers must distinguish stop reasons."""

    def __init__(self, code: str, *, status: int | None = None):
        super().__init__(code)
        self.code = code
        self.status = status


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_without_redirects():
    # One opener invocation must not fan out to another origin or another URL.
    return build_opener(ProxyHandler({}), _RejectRedirects()).open


class DetachedTmdbTransport:
    """Consume at most cap opener launches, including failed responses.

    No automatic retries, credential discovery, cache access, body logging,
    checkpoint writes or implicit use by the interactive client. A caller may
    retry transient failures with this same instance and budget. Injected callbacks
    must not re-enter the transport (including its counter properties).
    """

    def __init__(
        self,
        cap: int,
        *,
        bearer: Callable[[], str],
        cancelled: Callable[[], bool] = lambda: False,
        opener=None,
    ):
        if type(cap) is not int or cap < 0:
            raise ValueError("TMDb attempt cap must be a non-negative integer")
        self._cap = cap
        self._bearer = bearer
        self._cancelled = cancelled
        self._open = _open_without_redirects() if opener is None else opener
        self._attempts = self._denials = 0
        self._throttled = False
        self._lock = Lock()

    @property
    def attempts(self) -> int:
        with self._lock:
            return self._attempts

    @property
    def budget_denials(self) -> int:
        with self._lock:
            return self._denials

    def _check(self):
        if self._cancelled():
            raise DetachedTmdbError("cancelled")
        if self._throttled:
            raise DetachedTmdbError("throttled", status=429)
        if self._attempts >= self._cap:
            self._denials += 1
            raise DetachedTmdbError("budget_exhausted")

    def get(self, path: str, params: Mapping[str, object]) -> dict:
        if not isinstance(path, str) or not _ROUTE.fullmatch(path):
            raise DetachedTmdbError("invalid_route")
        if any(not isinstance(k, str) or k.casefold() in {"api_key", "authorization"} for k in params):
            raise DetachedTmdbError("invalid_parameter")
        query = None
        try:
            query = urlencode(list(params.items()), doseq=True)
        except (TypeError, ValueError, OSError, RuntimeError):
            pass
        if query is None:
            raise DetachedTmdbError("invalid_parameter")
        with self._lock:
            self._check()
        bearer = None
        try:
            bearer = self._bearer()
        except (OSError, RuntimeError, ValueError):
            pass
        if not isinstance(bearer, str) or not bearer or not bearer.isascii() or any(not 33 <= ord(c) <= 126 for c in bearer):
            raise DetachedTmdbError("invalid_credentials")
        request = Request(_ORIGIN + path + ("?" + query if query else ""), headers={
            "Accept": "application/json",
            "Authorization": "Bearer " + bearer,
        })
        # Serialize this detached run so the outcome of a 429 is known before
        # another launch can pass the guard. Read/decode failures remain billed.
        with self._lock:
            self._check()
            self._attempts += 1
            failure = None
            try:
                with self._open(request, timeout=_TIMEOUT_SECONDS) as response:
                    raw = response.read(_BODY_LIMIT + 1)
                if len(raw) > _BODY_LIMIT:
                    raise DetachedTmdbError("response_too_large")
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, dict):
                    raise DetachedTmdbError("invalid_response")
                return data
            except HTTPError as error:
                status = error.code
                if status == 429:
                    self._throttled = True
                failure = DetachedTmdbError(
                    "throttled" if status == 429 else "redirect" if 300 <= status < 400 else "http",
                    status=status,
                )
                error.close()
            except (URLError, OSError, HTTPException):
                failure = DetachedTmdbError("transport")
            except ValueError:
                failure = DetachedTmdbError("invalid_response")
            # Don't retain a transport exception carrying a credentialed Request
            # or a remote response body in the surfaced exception chain.
            raise failure
