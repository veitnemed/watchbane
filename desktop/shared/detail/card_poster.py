"""Poster display and context menu helpers for DetailCard."""

from __future__ import annotations

from collections import OrderedDict

from desktop.i18n import tr
from desktop.shared.detail.posters import get_poster_cache_directory, open_path_in_shell
from desktop.theme import build_poster_image_style, build_poster_placeholder_style

DETAIL_POSTER_SOURCE_CACHE_LIMIT = 16
_detail_poster_source_cache: OrderedDict[str, object] = OrderedDict()


def clear_detail_poster_source_cache(poster_path: str | None = None) -> None:
    """Clear cached detail poster pixmaps after a local poster file is replaced."""
    if poster_path in (None, ""):
        _detail_poster_source_cache.clear()
        return
    _detail_poster_source_cache.pop(str(poster_path), None)


def load_detail_poster_source_pixmap(poster_path: str):
    from PyQt6.QtGui import QPixmap

    cached = _detail_poster_source_cache.get(poster_path)
    if cached is not None:
        _detail_poster_source_cache.move_to_end(poster_path)
        return cached if cached is not False else None
    pixmap = QPixmap(poster_path)
    if pixmap.isNull():
        _detail_poster_source_cache[poster_path] = False
        while len(_detail_poster_source_cache) > DETAIL_POSTER_SOURCE_CACHE_LIMIT:
            _detail_poster_source_cache.popitem(last=False)
        return None
    _detail_poster_source_cache[poster_path] = pixmap
    while len(_detail_poster_source_cache) > DETAIL_POSTER_SOURCE_CACHE_LIMIT:
        _detail_poster_source_cache.popitem(last=False)
    return pixmap


def rounded_poster_pixmap_for_display(pixmap, radius: int):
    """Return a pixmap clipped to rounded corners."""
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QPainter, QPainterPath, QPixmap

    if pixmap.isNull() or radius <= 0:
        return pixmap

    rounded = QPixmap(pixmap.size())
    rounded.fill(Qt.GlobalColor.transparent)

    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(QRectF(rounded.rect()), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return rounded


def cover_crop_poster_pixmap_for_display(pixmap, width: int, height: int, radius: int = 0):
    """Scale and center-crop poster to fill the shell without distortion."""
    from PyQt6.QtCore import Qt

    if pixmap.isNull() or width <= 0 or height <= 0:
        return pixmap

    scaled = pixmap.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    crop_x = max(0, (scaled.width() - width) // 2)
    crop_y = max(0, (scaled.height() - height) // 2)
    cropped = scaled.copy(crop_x, crop_y, width, height)
    return rounded_poster_pixmap_for_display(cropped, radius)


class DetailCardPosterMixin:
    """Poster sync, placeholder and shell-open actions for detail cards."""

    def _sync_poster_display(self) -> None:
        from PyQt6.QtGui import QPixmap

        poster_width = self._profile.detail_poster_content_width
        poster_height = self._profile.detail_poster_content_height
        if self._poster_source_pixmap is not None and not self._poster_source_pixmap.isNull():
            display_pixmap = cover_crop_poster_pixmap_for_display(
                self._poster_source_pixmap,
                poster_width,
                poster_height,
                self._profile.detail_poster_content_radius,
            )
            self._poster_label.setFixedSize(poster_width, poster_height)
            self._poster_label.setStyleSheet(build_poster_image_style())
            self._poster_label.setText("")
            self._poster_label.setPixmap(display_pixmap)
            return

        self._poster_label.setFixedSize(poster_width, poster_height)
        if self._poster_label.pixmap() is None or self._poster_label.pixmap().isNull():
            self._poster_label.setPixmap(QPixmap())
            if self._poster_label.text() == "":
                self._poster_label.setText(tr("detail.poster.none"))
            self._poster_label.setStyleSheet(build_poster_placeholder_style())

    def _schedule_poster_height_sync(self) -> None:
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._sync_poster_display)

    def _set_poster_placeholder(self) -> None:
        from PyQt6.QtGui import QPixmap

        self._poster_source_pixmap = None
        self._poster_label.setPixmap(QPixmap())
        self._poster_label.setText(tr("detail.poster.none"))
        self._poster_label.setStyleSheet(build_poster_placeholder_style())

    def _set_poster_image(self, poster_path: str) -> bool:
        pixmap = load_detail_poster_source_pixmap(poster_path)
        if pixmap is None:
            return False

        self._poster_source_pixmap = pixmap
        self._sync_poster_display()
        return True

    def _set_local_poster_path(self, local_path: str | None) -> None:
        self._local_poster_path = local_path
        self._poster_label.setToolTip(local_path or "")

    def _show_poster_context_menu(self, position) -> None:
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self._poster_label)
        open_action = menu.addAction(tr("detail.poster.open"))
        open_action.setEnabled(self._local_poster_path is not None)
        cache_action = menu.addAction(tr("detail.poster.cache_folder"))
        chosen_action = menu.exec(self._poster_label.mapToGlobal(position))
        if chosen_action is open_action:
            self._open_local_poster()
        elif chosen_action is cache_action:
            self._open_poster_cache_directory()

    def _open_local_poster(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        if self._local_poster_path is None:
            return
        ok, error = open_path_in_shell(self._local_poster_path)
        if not ok:
            QMessageBox.warning(self._frame, "Poster", error or tr("detail.poster.error.open_file"))

    def _open_poster_cache_directory(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        cache_dir = get_poster_cache_directory()
        ok, error = open_path_in_shell(cache_dir)
        if not ok:
            QMessageBox.warning(
                self._frame,
                "Poster-cache",
                error or tr("detail.poster.error.open_cache"),
            )

    def apply_local_poster_path(self, poster_path: str | None) -> None:
        """Update only the poster area after async download."""
        if poster_path not in (None, "") and self._set_poster_image(poster_path):
            self._set_local_poster_path(poster_path)
        else:
            self._set_poster_placeholder()
        self._schedule_poster_height_sync()
