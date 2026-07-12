"""Shared Watchbane and TMDb logo helpers for desktop surfaces."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import QLabel

from desktop.theme.tokens import FILM_TEXT_SUBTLE, FONT_FAMILY


_IMAGE_ROOT = Path(__file__).resolve().parents[1] / "images"
WATCHBANE_SYMBOL_PATH = _IMAGE_ROOT / "logos" / "w_symbol_png.png"


def _scaled_pixmap(path: Path, width: int, height: int) -> QPixmap:
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return QPixmap()
    return pixmap.scaled(
        QSize(max(1, int(width)), max(1, int(height))),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def logo_label(
    pixmap: QPixmap,
    *,
    object_name: str,
    accessible_name: str,
) -> QLabel:
    label = QLabel()
    label.setObjectName(object_name)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setAccessibleName(accessible_name)
    label.setPixmap(pixmap)
    if not pixmap.isNull():
        label.setFixedSize(pixmap.size())
    return label


def watchbane_wordmark_label(width: int, height: int) -> QLabel:
    """Return a DPI-safe minimalist Watchbane text wordmark."""
    label = QLabel("Watchbane")
    label.setObjectName("watchbaneWordmark")
    label.setAccessibleName("Watchbane")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setFixedSize(max(1, int(width)), max(1, int(height)))
    font = QFont(FONT_FAMILY)
    font.setPixelSize(max(16, min(38, int(height * 0.42))))
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    label.setStyleSheet(
        f"QLabel#watchbaneWordmark {{ color: {FILM_TEXT_SUBTLE}; "
        "background: transparent; border: none; padding: 0; }}"
    )
    return label


def tmdb_logo_label(size: int) -> QLabel:
    """Return a crisp text attribution badge instead of scaling a raster logo."""
    label = QLabel("TMDb")
    label.setObjectName("tmdbAttributionLogo")
    label.setAccessibleName("TMDb")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setFixedSize(max(38, int(size * 1.5)), max(22, int(size * 0.6)))
    font = QFont(FONT_FAMILY)
    font.setPixelSize(max(11, int(size * 0.32)))
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    return label


def watchbane_symbol_label(size: int) -> QLabel:
    return logo_label(
        _scaled_pixmap(WATCHBANE_SYMBOL_PATH, size, size),
        object_name="watchbaneShellSymbol",
        accessible_name="Watchbane",
    )
