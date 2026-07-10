"""Runtime icon processing for the candidate filters reference layout."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QImage, QPixmap
from PyQt6.QtWidgets import QLabel


_SPRITE_PATH = (
    Path(__file__).resolve().parents[1]
    / "images"
    / "logos_for_start_select_menu"
    / "filters_menu"
    / "icons_for_use.png"
)
_SPRITE_COLUMNS = 5
_SPRITE_ROWS = 4
_ICON_CELLS = {
    "filter": (1, 0),
    "document": (2, 0),
    "globe": (3, 0),
    "media": (4, 0),
    "calendar": (1, 1),
    "heart": (2, 1),
    "vibe": (3, 1),
    "clock": (4, 1),
    "target": (0, 2),
    "refresh": (1, 2),
    "search": (3, 2),
    "replenish": (4, 2),
}
_pixmap_cache: dict[tuple[str, int, str], QPixmap] = {}


def _sprite() -> QImage:
    image = QImage(str(_SPRITE_PATH))
    if image.isNull():
        return QImage()
    return image.convertToFormat(QImage.Format.Format_RGB32)


def _source_cell(name: str) -> QImage:
    sprite = _sprite()
    if sprite.isNull():
        return QImage()
    column, row = _ICON_CELLS.get(name, _ICON_CELLS["document"])
    cell_width = sprite.width() // _SPRITE_COLUMNS
    cell_height = sprite.height() // _SPRITE_ROWS
    inset_x = max(1, cell_width // 14)
    inset_y = max(1, cell_height // 14)
    return sprite.copy(
        column * cell_width + inset_x,
        row * cell_height + inset_y,
        cell_width - inset_x * 2,
        cell_height - inset_y * 2,
    )


def _processed_icon_image(name: str, color: str) -> QImage:
    source = _source_cell(name)
    if source.isNull():
        return QImage()
    target = QImage(source.size(), QImage.Format.Format_ARGB32)
    target.fill(Qt.GlobalColor.transparent)
    tint = QColor(color)
    for y in range(source.height()):
        for x in range(source.width()):
            pixel = source.pixelColor(x, y)
            red = pixel.red()
            green = pixel.green()
            blue = pixel.blue()
            average = (red + green + blue) / 3
            chroma = max(red, green, blue) - min(red, green, blue)
            dark_alpha = max(0, 238 - average) * 2.9
            chroma_alpha = max(0, chroma - 12) * 3.6
            alpha = int(min(245, max(dark_alpha, chroma_alpha)))
            if alpha < 58:
                continue
            out = QColor(tint)
            out.setAlpha(min(245, max(82, int(alpha * 1.18))))
            target.setPixelColor(x, y, out)
    return _trim_transparent(target)


def _trim_transparent(image: QImage) -> QImage:
    left = image.width()
    top = image.height()
    right = -1
    bottom = -1
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() <= 0:
                continue
            left = min(left, x)
            top = min(top, y)
            right = max(right, x)
            bottom = max(bottom, y)
    if right < left or bottom < top:
        return image
    padding = max(2, min(image.width(), image.height()) // 18)
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image.width() - 1, right + padding)
    bottom = min(image.height() - 1, bottom + padding)
    return image.copy(left, top, right - left + 1, bottom - top + 1)


def filter_icon_pixmap(name: str, size: int, color: str) -> QPixmap:
    """Return a processed sprite icon as a square pixmap."""
    key = (name, int(size), color)
    cached = _pixmap_cache.get(key)
    if cached is not None:
        return cached
    image = _processed_icon_image(name, color)
    if image.isNull():
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
    else:
        pixmap = QPixmap.fromImage(image).scaled(
            QSize(size, size),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    _pixmap_cache[key] = pixmap
    return pixmap


def filter_icon(name: str, size: int, color: str) -> QIcon:
    """Return a QIcon built from the processed sprite."""
    return QIcon(filter_icon_pixmap(name, size, color))


def filter_icon_label(name: str, object_name: str, size: int, color: str) -> QLabel:
    """Return a fixed-size label displaying a processed sprite icon."""
    label = QLabel()
    label.setObjectName(object_name)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setFixedSize(size, size)
    label.setPixmap(filter_icon_pixmap(name, max(1, int(size * 0.9)), color))
    return label
