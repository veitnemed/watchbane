"""Circular deck reserve indicator for the recommendations feed header."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from candidates.deck_reserve_presentation import DeckReservePresentation

from desktop.i18n import tr
from desktop.theme.scaling import list_px
from desktop.theme.tokens import (
    FILM_RATING_TRACK,
    FILM_SURFACE_0,
    FILM_TEXT,
    FILM_TEXT_MUTED,
    FONT_FAMILY,
    TRANSPARENT_STYLE,
)

_RESERVE_LOW_COLOR = "#E85D5D"
_RESERVE_HIGH_COLOR = "#4ADE80"
_SPINNER_ARC_DEGREES = 90
_SPINNER_INTERVAL_MS = 33


def _lerp_channel(low: int, high: int, ratio: float) -> int:
    return int(round(low + (high - low) * ratio))


def _progress_color(ratio: float) -> QColor:
    clamped = max(0.0, min(1.0, ratio))
    low = QColor(_RESERVE_LOW_COLOR)
    high = QColor(_RESERVE_HIGH_COLOR)
    return QColor(
        _lerp_channel(low.red(), high.red(), clamped),
        _lerp_channel(low.green(), high.green(), clamped),
        _lerp_channel(low.blue(), high.blue(), clamped),
    )


class DeckReserveIndicator(QWidget):
    """Small circular reserve ring with percentage or transient status states."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("recommendationsDeckReserveIndicator")
        self.setStyleSheet(TRANSPARENT_STYLE)
        self.setAccessibleName(tr("recommendations.deck_reserve.label"))
        self._mode = "idle"
        self._progress = 0.0
        self._center_text = ""
        self._spinner_angle = 0
        self._widget_size = list_px(48)
        self._circle_diameter = list_px(40)
        self._ring_pen_width = max(list_px(3), 1)
        self._value_font_pixel = max(list_px(7), int(round(self._circle_diameter * 0.20)))
        self._spinner_timer: QTimer | None = None
        self.setFixedSize(self._widget_size, self._widget_size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.hide()

    def apply_presentation(self, presentation: DeckReservePresentation) -> None:
        self._stop_spinner()
        self._mode = presentation.mode
        if presentation.tooltip_key:
            description = tr(presentation.tooltip_key, **presentation.tooltip_kwargs)
            self.setToolTip(description)
            self.setAccessibleDescription(description)
        else:
            self.setToolTip("")
            self.setAccessibleDescription("")

        if presentation.mode == "idle":
            self.hide()
            return

        self.show()
        if presentation.mode in {"ready", "offline"} and presentation.snapshot is not None:
            snapshot = presentation.snapshot
            self._progress = snapshot.ratio
            self._center_text = "45+" if snapshot.remaining >= 45 else str(snapshot.remaining)
            self.update()
            return

        self._progress = 0.0
        if presentation.mode == "error":
            self._center_text = "!"
        else:
            self._center_text = ""
        if presentation.mode in {"loading", "replenishing"}:
            self._start_spinner()
        self.update()

    def progress(self) -> float:
        return self._progress

    def _start_spinner(self) -> None:
        self._spinner_angle = 0
        timer = QTimer(self)
        timer.setInterval(_SPINNER_INTERVAL_MS)
        timer.timeout.connect(self._advance_spinner)
        timer.start()
        self._spinner_timer = timer

    def _stop_spinner(self) -> None:
        if self._spinner_timer is None:
            return
        self._spinner_timer.stop()
        self._spinner_timer.deleteLater()
        self._spinner_timer = None

    def _advance_spinner(self) -> None:
        self._spinner_angle = (self._spinner_angle + 12) % 360
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        left = (self.width() - self._circle_diameter) / 2
        top = (self.height() - self._circle_diameter) / 2
        rect = QRectF(left, top, self._circle_diameter, self._circle_diameter)
        ring_rect = rect.adjusted(
            self._ring_pen_width,
            self._ring_pen_width,
            -self._ring_pen_width,
            -self._ring_pen_width,
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(FILM_SURFACE_0))
        painter.drawEllipse(rect)

        track_pen = QPen(QColor(FILM_RATING_TRACK), self._ring_pen_width)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(ring_rect, 90 * 16, -360 * 16)

        if self._mode in {"loading", "replenishing"}:
            spinner_pen = QPen(QColor(FILM_TEXT_MUTED), self._ring_pen_width)
            spinner_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(spinner_pen)
            painter.drawArc(
                ring_rect,
                (90 - self._spinner_angle) * 16,
                -_SPINNER_ARC_DEGREES * 16,
            )
        elif self._mode in {"ready", "offline"} and self._progress > 0:
            fill_pen = QPen(_progress_color(self._progress), self._ring_pen_width)
            fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(fill_pen)
            painter.drawArc(ring_rect, 90 * 16, -int(360 * 16 * self._progress))

        if self._center_text:
            painter.setPen(QPen(QColor(FILM_TEXT if self._mode != "error" else _RESERVE_LOW_COLOR)))
            value_font = QFont(FONT_FAMILY)
            value_font.setPixelSize(self._value_font_pixel)
            value_font.setBold(self._mode == "error")
            painter.setFont(value_font)
            inner_pad = max(list_px(9), int(self._circle_diameter * 0.22))
            text_rect = rect.adjusted(inner_pad, inner_pad * 0.5, -inner_pad, -inner_pad * 0.5)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._center_text)
