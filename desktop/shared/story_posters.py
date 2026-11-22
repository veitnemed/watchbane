"""Bounded direct-TMDb poster delivery for the two-section shell.

Reuses the existing preview cache and queue, never the legacy proxy fallback.
"""
import os
import re
import stat
import tempfile
from pathlib import Path
import weakref

from PyQt6.QtCore import QObject, QEvent, QUrl, QTimer, QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QImageReader, QPixmap
from PyQt6.QtNetwork import QNetworkRequest, QNetworkReply
from PyQt6 import sip
from candidates.story_artwork import is_provider_poster_path
from desktop.candidates.poster_prefetch import CandidatePosterPrefetchController
from posters.download_images import MAX_POSTER_BYTES, preview_poster_path_for_url

_PATTERN = re.compile(r'https://image\.tmdb\.org/t/p/(?:original|w\d{2,4})/([A-Za-z0-9_-]{1,160}\.(?:jpg|png|webp))\Z')

# Online card cache reads happen on the GUI thread. These caps apply only
# to that optional preview, never to ordinary local or full poster artwork.
_CACHED_PROVIDER_BYTES = 1024 * 1024
_CACHED_PROVIDER_WIDTH = 1024
_CACHED_PROVIDER_HEIGHT = 1536


def cdn_url(value):
    match = _PATTERN.fullmatch(str(value or ''))
    return 'https://image.tmdb.org/t/p/w342/' + match[1] if match else None


def image_reader_valid(reader):
    size = reader.size()
    return (bytes(reader.format()).lower() in (b'jpeg', b'png', b'webp')
            and 0 < size.width() <= 4096 and 0 < size.height() <= 4096
            and size.width() * size.height() <= 8_000_000)


def local_picture(path, size):
    from PyQt6.QtCore import Qt
    try:
        value = str(path or '')
        if not value or value.startswith(('//', '\\\\', 'http:', 'https:')): return None
        p = Path(value)
        if not p.is_file() or p.stat().st_size > MAX_POSTER_BYTES: return None
        reader = QImageReader(str(p))
        if not image_reader_valid(reader): return None
        reader.setScaledSize(reader.size().scaled(size, Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        return None if image.isNull() else QPixmap.fromImage(image)
    except (OSError, ValueError):
        return None


def cached_provider_picture(poster_path, size):
    """Read only exact, already cached TMDb artwork. No network or cache writes."""
    from PyQt6.QtCore import Qt

    if not is_provider_poster_path(poster_path):
        return None
    # The provider name never becomes a filesystem path. The trusted CDN URL
    # is only the input to our existing hashed local cache key.
    path = preview_poster_path_for_url("https://image.tmdb.org/t/p/w342" + poster_path).absolute()
    try:
        # Reject symlinks (including a redirected preview directory) before
        # opening. O_NOFOLLOW adds descriptor-time protection where available.
        if path.resolve(strict=True) != path:
            return None
        meta = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= _CACHED_PROVIDER_BYTES:
            return None
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or not os.path.samestat(meta, opened)
                    or path.resolve(strict=True) != path or not 0 < opened.st_size <= _CACHED_PROVIDER_BYTES):
                return None
            data = stream.read(_CACHED_PROVIDER_BYTES + 1)
        if not 0 < len(data) <= _CACHED_PROVIDER_BYTES:
            return None
        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer)
        source_size = reader.size()
        if (not image_reader_valid(reader) or source_size.width() > _CACHED_PROVIDER_WIDTH
                or source_size.height() > _CACHED_PROVIDER_HEIGHT):
            return None
        scaled_size = source_size.scaled(size, Qt.AspectRatioMode.KeepAspectRatio)
        reader.setScaledSize(scaled_size)
        image = reader.read()
        if (image.isNull() or image.width() > scaled_size.width()
                or image.height() > scaled_size.height()):
            return None
        return QPixmap.fromImage(image)
    except (OSError, ValueError, RuntimeError):
        return None


class DirectPosterController(CandidatePosterPrefetchController):
    def __init__(self, parent=None):
        super().__init__(max_concurrent=2, parent=parent)

    def cancel_pending(self):
        cancelled = set(self._active.values())
        super().cancel_pending()
        self._attempted_urls.difference_update(cancelled)
        for url in cancelled: self._failed_at.pop(url, None)

    def retain_queued_urls(self, urls):
        """Drop not-yet-started downloads for cards that left the viewport."""
        discarded = self._queued_urls - urls
        if not discarded:
            return
        self._queue = type(self._queue)(url for url in self._queue if url in urls)
        self._queued_urls.difference_update(discarded)
        for url in discarded:
            self._waiters.pop(url, None)
        self._update_busy()

    def _pump(self):
        while self._queue and len(self._active) < self._max_concurrent:
            source = self._queue.popleft(); self._queued_urls.discard(source)
            url = cdn_url(source)
            if not url or self._host_is_in_cooldown(source):
                self._finish_url(source, None); continue
            request = QNetworkRequest(QUrl(url))
            request.setTransferTimeout(8000)
            request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
            request.setAttribute(QNetworkRequest.Attribute.CookieLoadControlAttribute, QNetworkRequest.LoadControl.Manual)
            request.setAttribute(QNetworkRequest.Attribute.CookieSaveControlAttribute, QNetworkRequest.LoadControl.Manual)
            request.setRawHeader(b'Accept', b'image/jpeg,image/png,image/webp')
            reply = self._manager.get(request)
            reply.setReadBufferSize(MAX_POSTER_BYTES + 1)
            self._active[reply] = source
            reply.readyRead.connect(lambda r=reply: r.abort() if r.bytesAvailable() > MAX_POSTER_BYTES else None)
            reply.finished.connect(lambda r=reply: self._on_reply_finished(r))

    def _on_reply_finished(self, reply):
        source = self._active.pop(reply, '')
        path = None
        if (reply.error() == QNetworkReply.NetworkError.NoError
                and reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) == 200):
            data = bytes(reply.readAll())
            if 0 < len(data) <= MAX_POSTER_BYTES:
                buffer = QBuffer(); buffer.setData(QByteArray(data)); buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                reader = QImageReader(buffer)
                if image_reader_valid(reader) and not reader.read().isNull():
                    path = self._write_preview(source, data)
        elif self._is_host_network_failure(reply.error()):
            self._suspend_host(source, reply.error(), reply.errorString())
        reply.deleteLater(); self._finish_url(source, path); self._pump(); self._update_busy()

    @staticmethod
    def _write_preview(source, data):
        temporary = None
        try:
            dest = preview_poster_path_for_url(source); dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as f:
                temporary = Path(f.name); f.write(data); f.flush(); os.fsync(f.fileno())
            temporary.replace(dest)
            return str(dest)
        except OSError:
            return None
        finally:
            if temporary is not None: temporary.unlink(missing_ok=True)

    def enqueue(self, identity, poster_url, **kwargs):
        url = cdn_url(poster_url)
        if url: super().enqueue(identity, url, **kwargs)


class CardPosters(QObject):
    """Widget lifetime/generation adapter; only visible cards enter the queue."""
    def __init__(self, widget):
        super().__init__(widget)
        self.widget = widget; self.controller = DirectPosterController(self)
        self.labels = {}; self.generation = 0; self.serial = 0
        self.controller.poster_ready.connect(self._ready)
        widget.installEventFilter(self)
        self.timer = QTimer(self); self.timer.setInterval(200)
        self.timer.timeout.connect(self._visible); self.timer.start()

    def clear(self):
        self.generation += 1; self.labels.clear(); self.controller.cancel_pending()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Hide:
            self.controller.cancel_pending()
        elif event.type() == QEvent.Type.Show:
            self.controller.allow_failed_retries(minimum_age_seconds=30)
            QTimer.singleShot(0, self._visible)
        return False

    def bind(self, label, candidate, title):
        from desktop.candidates.presenters import resolve_local_poster_path_for_candidate, _candidate_poster_hints
        try:
            path = resolve_local_poster_path_for_candidate(candidate)
            picture = local_picture(path, label.size())
            if picture is not None:
                label.setPixmap(picture); label.setAccessibleName('Постер: ' + title); return
            url = cdn_url(_candidate_poster_hints(candidate, data_language='ru').get('poster_url'))
        except (OSError, ValueError, TypeError):
            return
        if not url: return
        # A corrupt cache must not permanently suppress a retry.
        cached = preview_poster_path_for_url(url)
        if cached.is_file() and local_picture(cached, label.size()) is None:
            try: cached.unlink()
            except OSError: return
        self.serial += 1
        identity = f'{self.generation}:{self.serial}'
        self.labels[identity] = (weakref.ref(label), url, title)
        if len(self.labels) == 1:
            QTimer.singleShot(0, self._visible)

    def _visible(self):
        if not self.widget.isVisible():
            return
        visible = []
        for identity, (label_ref, url, _) in list(self.labels.items()):
            label = label_ref()
            if label is None or sip.isdeleted(label):
                self.labels.pop(identity, None)
            elif not label.visibleRegion().isEmpty():
                visible.append((identity, url))
        self.controller.retain_queued_urls({url for _, url in visible})
        for identity, url in visible:
            if len(self.controller._queue) < 40:
                self.controller.enqueue(identity, url)

    def _ready(self, identity, path):
        entry = self.labels.get(identity)
        if not entry: return
        label = entry[0]()
        if label is None or sip.isdeleted(label): return
        picture = local_picture(path, label.size())
        if picture is not None:
            label.setPixmap(picture); label.setAccessibleName('Постер: ' + entry[2])
            self.labels.pop(identity, None)
