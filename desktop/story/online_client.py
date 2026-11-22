"""Opt-in transport for a separately started Watchbane loopback story server."""
from dataclasses import dataclass, replace
from http.client import HTTPConnection, HTTPException
import json
import re
from socket import SHUT_RDWR
from threading import Event, Thread
from time import monotonic

from candidates.story_artwork import is_provider_poster_path

_HOST = "127.0.0.1"
_PATH = "/v1/search"
_TIMEOUT = 8.0
_MAX_BYTES = 512 * 1024
_MAX_BUSY_BYTES = 256
_OUTCOME_HEADER = "Watchbane-Search-Outcome"
_ARTWORK_HEADER = "Watchbane-Search-Artwork"
_OUTCOME_V1 = frozenset({
    ("candidates", "possible_local_results"),
    ("scope_refusal", "explicit_non_film_request"),
    ("clarification", "unsupported_exclusion"),
    ("clarification", "need_plot_detail"),
    ("clarification", "no_eligible_catalog_entries"),
    ("clarification", "no_candidates"),
})
_RESULT_KEYS = {"id", "media_type", "title", "year", "overview", "evidence", "language"}
_ID = re.compile(r"tmdb:(movie|tv):([1-9][0-9]{0,18})", re.ASCII)


class OnlineStoryError(RuntimeError):
    """Fixed, display-safe error; never includes the request or response body."""


class OnlineStoryBusy(OnlineStoryError):
    """The loopback server is handling another search; never retried automatically."""


@dataclass(frozen=True)
class OnlineStoryResult:
    id: str
    media_type: str
    title: str
    year: int | None
    overview: str
    evidence: str
    poster_path: str | None = None


@dataclass(frozen=True)
class OnlineStoryOutcome:
    results: tuple[OnlineStoryResult, ...]
    state: str
    reason: str


def _invalid_response():
    return OnlineStoryError("Invalid response from the local story server.")


def _unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError
    return result


def _is_busy(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object) == {"detail": "search_busy"}
    except (ValueError, RecursionError):
        return False


def _parse(raw, limit, *, with_outcome=False, with_artwork=False):
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        keys = {"source", "results", "outcome"} if with_outcome else {"source", "results"}
        if with_artwork:
            keys.add("artwork")
        if (type(value) is not dict or set(value) != keys or value["source"] != "tmdb"
                or type(value["results"]) is not list or len(value["results"]) > limit):
            raise ValueError
        results, seen = [], set()
        for row in value["results"]:
            if type(row) is not dict or set(row) != _RESULT_KEYS or row["language"] != "ru-RU":
                raise ValueError
            identifier = row["id"]
            match = _ID.fullmatch(identifier) if type(identifier) is str else None
            if not match or match[1] != row["media_type"] or int(match[2]) > (1 << 63)-1 or identifier in seen:
                raise ValueError
            year = row["year"]
            if year is not None and (type(year) is not int or not 1800 <= year <= 2200):
                raise ValueError
            for key, maximum in (("title", 512), ("overview", 8192), ("evidence", 8192)):
                field = row[key]
                if (type(field) is not str or len(field) > maximum or "\x00" in field
                        or (key != "evidence" and not field.strip())):
                    raise ValueError
                field.encode("utf-8")
            results.append(OnlineStoryResult(identifier, row["media_type"], row["title"],
                                             year, row["overview"], row["evidence"]))
            seen.add(identifier)
        if with_artwork:
            artwork = value["artwork"]
            if (type(artwork) is not dict or not artwork.keys() <= seen
                    or not all(is_provider_poster_path(path) for path in artwork.values())):
                raise ValueError
            results = [replace(row, poster_path=artwork.get(row.id)) for row in results]
        if with_outcome:
            outcome = value["outcome"]
            if type(outcome) is not dict or set(outcome) != {"state", "reason"}:
                raise ValueError
            state, reason = outcome["state"], outcome["reason"]
            if type(state) is not str or type(reason) is not str or (state, reason) not in _OUTCOME_V1:
                raise ValueError
            if bool(results) != (state == "candidates"):
                raise ValueError
            return OnlineStoryOutcome(tuple(results), state, reason)
        return tuple(results)
    except (ValueError, RecursionError):
        raise _invalid_response() from None


def search_online(
    query: str,
    *,
    consent: bool = False,
    port: int = 8765,
    limit: int = 5,
    cancelled: Event | None = None,
    with_outcome: bool = False,
    with_artwork: bool = False,
) -> tuple[OnlineStoryResult, ...] | OnlineStoryOutcome:
    """Send only query/limit to IPv4 loopback; never discover a server or fall back.

    Call from a worker. The caller owns the explicit, per-request consent and may
    set the cancellation event. Cancellation stops local waiting, not a server
    operation that already received the POST. The optional outcome protocol
    requires the exact server echo and never retries with the legacy contract.
    Opt-in artwork also requires an exact echo; it returns opaque provider
    names only, with no image rendering, resolution, or extra I/O.
    """
    if consent is not True:
        raise OnlineStoryError("Local server search was not authorized.")
    if (type(port) is not int or not 1 <= port <= 65535 or type(limit) is not int or not 1 <= limit <= 10
            or type(query) is not str or len(query) > 600 or not query.strip()
            or type(with_outcome) is not bool or type(with_artwork) is not bool):
        raise OnlineStoryError("Invalid local story search request.")
    try:
        body = json.dumps({"query": query.strip(), "limit": limit}, ensure_ascii=False).encode("utf-8")
    except UnicodeError:
        raise OnlineStoryError("Invalid local story search request.") from None
    deadline = monotonic() + _TIMEOUT

    def check_active():
        if cancelled is not None and cancelled.is_set():
            raise OnlineStoryError("Local story search was cancelled.")
        if monotonic() >= deadline:
            raise OnlineStoryError("Local story search timed out.")

    check_active()
    connection = HTTPConnection(_HOST, port, timeout=_TIMEOUT)
    finished = Event()
    watcher = None
    try:
        # Direct stdlib connection: no proxy, ambient auth, cookies or redirect
        # handling. Keep the socket even if HTTPConnection detaches it on reply.
        connection.connect()
        stream = connection.sock
        check_active()

        def interrupt():
            while not finished.wait(0.05):
                if ((cancelled is not None and cancelled.is_set()) or monotonic() >= deadline):
                    try:
                        stream.shutdown(SHUT_RDWR)
                    except OSError:
                        pass
                    return

        # Socket timeout alone is an idle timeout; this also bounds slow headers
        # and interrupts reads while they are blocked.
        watcher = Thread(target=interrupt, daemon=True)
        watcher.start()
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "Accept-Encoding": "identity", "Cache-Control": "no-store"}
        if with_outcome:
            headers[_OUTCOME_HEADER] = "1"
        if with_artwork:
            headers[_ARTWORK_HEADER] = "1"
        connection.request("POST", _PATH, body, headers)
        check_active()
        with connection.getresponse() as response:
            check_active()
            busy_candidate = response.status == 503
            if response.status != 200 and not busy_candidate:
                raise OnlineStoryError("Local story server is unavailable.")

            def invalid():
                if busy_candidate:
                    return OnlineStoryError("Local story server is unavailable.")
                return _invalid_response()

            maximum = _MAX_BUSY_BYTES if busy_candidate else _MAX_BYTES
            if not busy_candidate and with_outcome and response.getheader(_OUTCOME_HEADER) != "1":
                raise invalid()
            if not busy_candidate and with_artwork and response.getheader(_ARTWORK_HEADER) != "1":
                raise invalid()
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
            encoding = response.getheader("Content-Encoding", "identity").strip().lower()
            size = response.getheader("Content-Length")
            if content_type != "application/json" or encoding != "identity":
                raise invalid()
            if size is not None and (not size.isascii() or not size.isdecimal() or len(size) > 9
                                     or not 0 < int(size) <= maximum):
                raise invalid()
            raw = bytearray()
            while True:
                check_active()
                chunk = response.read1(min(16384, maximum - len(raw) + 1))
                check_active()
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > maximum:
                    raise invalid()
            if size is not None and len(raw) != int(size):
                raise invalid()
            if busy_candidate:
                recognized = _is_busy(raw)
                check_active()
                if recognized:
                    raise OnlineStoryBusy("Local story server is busy.")
                raise invalid()
        parser_options = {}
        if with_outcome:
            parser_options["with_outcome"] = True
        if with_artwork:
            parser_options["with_artwork"] = True
        results = _parse(raw, limit, **parser_options)
        check_active()  # A superseded request cannot hand stale results back.
        return results
    except (OSError, HTTPException):
        check_active()
        raise OnlineStoryError("Local story server is unavailable.") from None
    finally:
        finished.set()
        connection.close()
        if watcher is not None:
            watcher.join()
