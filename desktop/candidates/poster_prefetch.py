"""Bounded, non-blocking poster prefetch for the recommendations feed."""

from __future__ import annotations

from collections import defaultdict, deque
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


class CandidatePosterPrefetchController(QObject):
    """Download a small number of posters concurrently without blocking Qt."""

    poster_ready = pyqtSignal(str, str)
    busy_changed = pyqtSignal(bool)
    batch_finished = pyqtSignal(int, int)

    def __init__(self, *, max_concurrent: int = 4, parent=None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._max_concurrent = max(1, int(max_concurrent))
        self._queue: deque[str] = deque()
        self._queued_urls: set[str] = set()
        self._waiters: dict[str, set[str]] = defaultdict(set)
        self._active: dict[QNetworkReply, str] = {}
        self._attempted_urls: set[str] = set()
        self._failed_at: dict[str, float] = {}
        self._busy = False
        self._batch_succeeded = 0
        self._batch_failed = 0

    def enqueue(self, identity: str, poster_url: str, *, priority: bool = False) -> None:
        identity = str(identity or "").strip()
        url = str(poster_url or "").strip()
        if not identity or not url.startswith(("http://", "https://")):
            return

        cached_path = local_preview_poster_path_if_cached(url)
        if cached_path is not None:
            self.poster_ready.emit(identity, cached_path)
            return
        if url in self._attempted_urls:
            failed_at = self._failed_at.get(url)
            if not priority or failed_at is None or monotonic() - failed_at < 5.0:
                return
            self._attempted_urls.discard(url)

        self._waiters[url].add(identity)
        if url in self._queued_urls:
            if priority:
                self._queue.remove(url)
                self._queue.appendleft(url)
            return
        if url in self._active.values():
            return
        if priority:
            self._queue.appendleft(url)
        else:
            self._queue.append(url)
        self._queued_urls.add(url)
        self._pump()
        self._update_busy()

    def allow_failed_retries(self, *, minimum_age_seconds: float = 30.0) -> None:
        """Permit a later tab activation to retry posters after network recovery."""
        cutoff = monotonic() - max(0.0, float(minimum_age_seconds))
        retryable = {url for url, failed_at in self._failed_at.items() if failed_at <= cutoff}
        self._attempted_urls.difference_update(retryable)

    def enqueue_candidates(self, candidates: list[dict], *, data_language: str) -> None:
        from desktop.candidates.presenters import (
            candidate_detail_identity,
            candidate_poster_url_for_download,
        )

        for candidate in candidates:
            url = candidate_poster_url_for_download(candidate, data_language=data_language)
            if url is None:
                continue
            self.enqueue(candidate_detail_identity(candidate), url)

    def _pump(self) -> None:
        while self._queue and len(self._active) < self._max_concurrent:
            source_url = self._queue.popleft()
            self._queued_urls.discard(source_url)
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
        if reply.error() == QNetworkReply.NetworkError.NoError:
            content = bytes(reply.readAll())
            if 0 < len(content) <= MAX_POSTER_BYTES and not QImage.fromData(content).isNull():
                local_path = self._write_preview(source_url, content)
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
            self._batch_succeeded = 0
            self._batch_failed = 0
        self.busy_changed.emit(busy)
        if was_busy and not busy:
            self.batch_finished.emit(self._batch_succeeded, self._batch_failed)

    def _finish_url(self, source_url: str, local_path: str | None) -> None:
        self._attempted_urls.add(source_url)
        identities = self._waiters.pop(source_url, set())
        if local_path is None:
            self._failed_at[source_url] = monotonic()
            self._batch_failed += len(identities)
            return
        self._failed_at.pop(source_url, None)
        self._batch_succeeded += len(identities)
        for identity in identities:
            self.poster_ready.emit(identity, local_path)

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
