"""Bounded, generation-safe poster prefetch for the recommendations feed."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import logging
from pathlib import Path
from time import monotonic

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from posters.download_images import (
    MAX_POSTER_BYTES,
    build_poster_request_headers,
    local_preview_poster_path_if_cached,
    normalize_tmdb_poster_download_url,
    preview_poster_path_for_url,
)


POSTER_PREFETCH_MAX_CONCURRENT = 4
POSTER_NETWORK_FAILURE_COOLDOWN_SECONDS = 60.0

logger = logging.getLogger(__name__)


@dataclass
class _PosterBatch:
    batch_id: int
    total: int
    ready: int = 0
    failed: int = 0
    settled: int = 0
    cache_hits: int = 0
    settled_identities: set[str] = field(default_factory=set)
    finished: bool = False


class CandidatePosterPrefetchController(QObject):
    """Download poster previews without blocking Qt or leaking stale batch state."""

    poster_ready = pyqtSignal(str, str)
    busy_changed = pyqtSignal(bool)
    network_cycle_finished = pyqtSignal(int, int)
    batch_started = pyqtSignal(int, int)
    candidate_settled = pyqtSignal(int, str, str, bool, bool)
    batch_progress = pyqtSignal(int, int, int, int, int, int)
    batch_finished = pyqtSignal(int, int, int, int, int)

    def __init__(
        self,
        *,
        max_concurrent: int = POSTER_PREFETCH_MAX_CONCURRENT,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._max_concurrent = max(1, int(max_concurrent))
        self._queue: deque[str] = deque()
        self._queued_urls: set[str] = set()
        self._waiters: dict[str, set[tuple[str, int | None]]] = defaultdict(set)
        self._active: dict[QNetworkReply, str] = {}
        self._attempted_urls: set[str] = set()
        self._failed_at: dict[str, float] = {}
        self._unavailable_hosts: dict[str, float] = {}
        self._busy = False
        self._network_succeeded = 0
        self._network_failed = 0
        self._next_batch_id = 0
        self._batch: _PosterBatch | None = None

    def enqueue(self, identity: str, poster_url: str, *, priority: bool = False) -> None:
        """Queue one background poster request outside the reveal-gated batch."""
        self._enqueue_waiter(
            identity,
            poster_url,
            batch_id=None,
            priority=priority,
            defer_pump=False,
        )

    def allow_failed_retries(self, *, minimum_age_seconds: float = 30.0) -> None:
        """Permit a later tab activation to retry posters after network recovery."""
        cutoff = monotonic() - max(0.0, float(minimum_age_seconds))
        retryable = {url for url, failed_at in self._failed_at.items() if failed_at <= cutoff}
        self._attempted_urls.difference_update(retryable)

    def enqueue_candidates(self, candidates: list[dict], *, data_language: str) -> None:
        """Prefetch candidates in the background without replacing the active batch."""
        from desktop.candidates.presenters import (
            candidate_detail_identity,
            candidate_poster_url_for_download,
        )

        for candidate in candidates:
            url = candidate_poster_url_for_download(candidate, data_language=data_language)
            if url is None:
                continue
            self.enqueue(candidate_detail_identity(candidate), url)

    def start_batch(
        self,
        candidates: list[dict],
        *,
        data_language: str,
        priority_count: int,
    ) -> int:
        """Start a replacement-deck batch and return its monotonically increasing id."""
        from desktop.candidates.presenters import (
            candidate_detail_identity,
            candidate_poster_url_for_download,
            resolve_local_poster_path_for_candidate,
        )

        unique_candidates: list[tuple[str, dict]] = []
        seen_identities: set[str] = set()
        for candidate in candidates:
            identity = str(candidate_detail_identity(candidate) or "").strip()
            if not identity or identity in seen_identities:
                continue
            seen_identities.add(identity)
            unique_candidates.append((identity, candidate))

        self._drop_replaced_waiters()
        self._network_succeeded = 0
        self._network_failed = 0

        self._next_batch_id += 1
        batch_id = self._next_batch_id
        self._batch = _PosterBatch(batch_id=batch_id, total=len(unique_candidates))
        self.batch_started.emit(batch_id, len(unique_candidates))
        self._emit_batch_progress(self._batch)

        priority_urls: list[str] = []
        priority_limit = max(0, int(priority_count))
        for position, (identity, candidate) in enumerate(unique_candidates):
            local_path = resolve_local_poster_path_for_candidate(
                candidate,
                data_language=data_language,
            )
            if local_path not in (None, ""):
                path = str(local_path)
                self.poster_ready.emit(identity, path)
                self._settle_batch_candidate(
                    batch_id,
                    identity,
                    local_path=path,
                    failed=False,
                    cache_hit=True,
                )
                continue

            url = candidate_poster_url_for_download(candidate, data_language=data_language)
            if url in (None, ""):
                self._settle_batch_candidate(
                    batch_id,
                    identity,
                    local_path=None,
                    failed=False,
                    cache_hit=False,
                )
                continue

            source_url = str(url)
            queued = self._enqueue_waiter(
                identity,
                source_url,
                batch_id=batch_id,
                priority=position < priority_limit,
                defer_pump=True,
            )
            if queued and position < priority_limit:
                priority_urls.append(source_url)

        self._prioritize_urls(priority_urls)
        self._pump()
        self._update_busy()
        batch = self._batch
        if batch is not None and batch.batch_id == batch_id and batch.total == 0:
            self._finish_batch(batch)
        return batch_id

    def _enqueue_waiter(
        self,
        identity: str,
        poster_url: str,
        *,
        batch_id: int | None,
        priority: bool,
        defer_pump: bool,
    ) -> bool:
        identity = str(identity or "").strip()
        url = str(poster_url or "").strip()
        if not identity or not url.startswith(("http://", "https://")):
            if batch_id is not None:
                self._settle_batch_candidate(
                    batch_id,
                    identity,
                    local_path=None,
                    failed=False,
                    cache_hit=False,
                )
            return False

        cached_path = local_preview_poster_path_if_cached(url)
        if cached_path is not None:
            path = str(cached_path)
            self.poster_ready.emit(identity, path)
            if batch_id is not None:
                self._settle_batch_candidate(
                    batch_id,
                    identity,
                    local_path=path,
                    failed=False,
                    cache_hit=True,
                )
            return False

        if url in self._attempted_urls:
            failed_at = self._failed_at.get(url)
            can_retry = priority and failed_at is not None and monotonic() - failed_at >= 5.0
            if not can_retry:
                if batch_id is not None:
                    self._settle_batch_candidate(
                        batch_id,
                        identity,
                        local_path=None,
                        failed=failed_at is not None,
                        cache_hit=False,
                    )
                return False
            self._attempted_urls.discard(url)

        waiters = self._waiters[url]
        if not any(waiter_identity == identity for waiter_identity, _batch_id in waiters):
            waiters.add((identity, batch_id))
        if url in self._queued_urls:
            if priority:
                self._queue.remove(url)
                self._queue.appendleft(url)
            return True
        if url in self._active.values():
            return True
        if priority:
            self._queue.appendleft(url)
        else:
            self._queue.append(url)
        self._queued_urls.add(url)
        if not defer_pump:
            self._pump()
            self._update_busy()
        return True

    def _drop_replaced_waiters(self) -> None:
        """Detach all item events from the deck being fully replaced."""
        self._waiters.clear()
        self._queue.clear()
        self._queued_urls.clear()

    def _prioritize_urls(self, urls: list[str]) -> None:
        priority = []
        seen: set[str] = set()
        for url in urls:
            if url in self._queued_urls and url not in seen:
                seen.add(url)
                priority.append(url)
        if not priority:
            return
        self._queue = deque(priority + [url for url in self._queue if url not in seen])

    def _pump(self) -> None:
        while self._queue and len(self._active) < self._max_concurrent:
            source_url = self._queue.popleft()
            self._queued_urls.discard(source_url)
            if self._host_is_in_cooldown(source_url):
                self._finish_url(source_url, None)
                continue
            download_url = normalize_tmdb_poster_download_url(source_url)
            if download_url is None:
                self._finish_url(source_url, None)
                continue

            request = QNetworkRequest(QUrl(download_url))
            request.setTransferTimeout(15_000)
            for name, value in build_poster_request_headers(download_url).items():
                if name.casefold() == "connection":
                    continue
                request.setRawHeader(name.encode("ascii"), value.encode("utf-8"))
            reply = self._manager.get(request)
            self._active[reply] = source_url
            reply.downloadProgress.connect(
                lambda received, _total, current=reply: current.abort()
                if received > MAX_POSTER_BYTES
                else None
            )
            reply.finished.connect(lambda current=reply: self._on_reply_finished(current))

    def _on_reply_finished(self, reply: QNetworkReply) -> None:
        source_url = self._active.pop(reply, "")
        local_path = None
        network_error = reply.error()
        if network_error == QNetworkReply.NetworkError.NoError:
            content = bytes(reply.readAll())
            if 0 < len(content) <= MAX_POSTER_BYTES and not QImage.fromData(content).isNull():
                local_path = self._write_preview(source_url, content)
        elif self._is_host_network_failure(network_error):
            self._suspend_host(source_url, network_error, reply.errorString())
        reply.deleteLater()
        self._finish_url(source_url, local_path)
        self._pump()
        self._update_busy()

    def _update_busy(self) -> None:
        busy = bool(self._queue or self._active)
        if busy == self._busy:
            return
        was_busy = self._busy
        self._busy = busy
        if busy and not was_busy:
            self._network_succeeded = 0
            self._network_failed = 0
        self.busy_changed.emit(busy)
        if was_busy and not busy:
            self.network_cycle_finished.emit(
                self._network_succeeded,
                self._network_failed,
            )

    def _finish_url(self, source_url: str, local_path: str | None) -> None:
        if not source_url:
            return
        self._attempted_urls.add(source_url)
        waiters = self._waiters.pop(source_url, set())
        if local_path is None:
            self._failed_at[source_url] = monotonic()
            self._network_failed += len(waiters)
            for identity, batch_id in waiters:
                if batch_id is not None:
                    self._settle_batch_candidate(
                        batch_id,
                        identity,
                        local_path=None,
                        failed=True,
                        cache_hit=False,
                    )
            return

        path = str(local_path)
        self._failed_at.pop(source_url, None)
        self._network_succeeded += len(waiters)
        for identity, batch_id in waiters:
            self.poster_ready.emit(identity, path)
            if batch_id is not None:
                self._settle_batch_candidate(
                    batch_id,
                    identity,
                    local_path=path,
                    failed=False,
                    cache_hit=False,
                )

    def _host_is_in_cooldown(self, source_url: str) -> bool:
        host = self._host_for_url(source_url)
        if host == "":
            return False
        until = self._unavailable_hosts.get(host)
        if until is None:
            return False
        if until > monotonic():
            return True
        self._unavailable_hosts.pop(host, None)
        return False

    def _suspend_host(
        self,
        source_url: str,
        network_error: QNetworkReply.NetworkError,
        error_text: str,
    ) -> None:
        host = self._host_for_url(source_url)
        if host == "":
            return
        self._unavailable_hosts[host] = monotonic() + POSTER_NETWORK_FAILURE_COOLDOWN_SECONDS
        logger.info(
            "candidate poster host paused host=%s error=%s detail=%s cooldown_seconds=%.0f",
            host,
            network_error.name,
            str(error_text or ""),
            POSTER_NETWORK_FAILURE_COOLDOWN_SECONDS,
        )

    @staticmethod
    def _host_for_url(source_url: str) -> str:
        return QUrl(str(source_url or "")).host().casefold()

    @staticmethod
    def _is_host_network_failure(network_error: QNetworkReply.NetworkError) -> bool:
        return network_error in {
            QNetworkReply.NetworkError.ConnectionRefusedError,
            QNetworkReply.NetworkError.RemoteHostClosedError,
            QNetworkReply.NetworkError.HostNotFoundError,
            QNetworkReply.NetworkError.TimeoutError,
            QNetworkReply.NetworkError.TemporaryNetworkFailureError,
            QNetworkReply.NetworkError.NetworkSessionFailedError,
            QNetworkReply.NetworkError.BackgroundRequestNotAllowedError,
            QNetworkReply.NetworkError.TooManyRedirectsError,
            QNetworkReply.NetworkError.InsecureRedirectError,
            QNetworkReply.NetworkError.UnknownNetworkError,
            QNetworkReply.NetworkError.UnknownProxyError,
            QNetworkReply.NetworkError.UnknownContentError,
            QNetworkReply.NetworkError.ProtocolUnknownError,
            QNetworkReply.NetworkError.ProtocolInvalidOperationError,
            QNetworkReply.NetworkError.SslHandshakeFailedError,
        }

    def _settle_batch_candidate(
        self,
        batch_id: int,
        identity: str,
        *,
        local_path: str | None,
        failed: bool,
        cache_hit: bool,
    ) -> None:
        batch = self._batch
        if (
            batch is None
            or batch.batch_id != batch_id
            or batch.finished
            or identity in batch.settled_identities
        ):
            return
        batch.settled_identities.add(identity)
        batch.settled += 1
        if local_path not in (None, ""):
            batch.ready += 1
        if failed:
            batch.failed += 1
        if cache_hit:
            batch.cache_hits += 1
        self.candidate_settled.emit(
            batch_id,
            identity,
            str(local_path or ""),
            bool(failed),
            bool(cache_hit),
        )
        self._emit_batch_progress(batch)
        if batch.settled >= batch.total:
            self._finish_batch(batch)

    def _emit_batch_progress(self, batch: _PosterBatch) -> None:
        self.batch_progress.emit(
            batch.batch_id,
            batch.ready,
            batch.failed,
            batch.settled,
            batch.total,
            batch.cache_hits,
        )

    def _finish_batch(self, batch: _PosterBatch) -> None:
        if batch.finished:
            return
        batch.finished = True
        self.batch_finished.emit(
            batch.batch_id,
            batch.ready,
            batch.failed,
            batch.total,
            batch.cache_hits,
        )

    @staticmethod
    def _write_preview(source_url: str, content: bytes) -> str | None:
        try:
            destination = preview_poster_path_for_url(source_url)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(f"{destination}.tmp")
            temporary.write_bytes(content)
            temporary.replace(destination)
            return str(destination)
        except OSError:
            return None
