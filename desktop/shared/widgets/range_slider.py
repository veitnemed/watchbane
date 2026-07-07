"""Compact two-handle horizontal range slider for desktop filters."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from desktop.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_SOFT,
    COLOR_BORDER,
    COLOR_CARD_ALT,
    COLOR_TEXT,
    layout_px,
)


def _slider_height() -> int:
    return max(34, layout_px(34))


def _handle_radius() -> int:
    return max(8, layout_px(8))


def _track_height() -> int:
    return max(5, layout_px(5))


def _edge_padding() -> int:
    return max(2, layout_px(2))


class RangeSlider(QWidget):
    """Compact two-handle horizontal range slider."""

    rangeChanged = pyqtSignal(int, int)

    def __init__(self, minimum: int, maximum: int, lower: int, upper: int, parent=None) -> None:
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._lower = lower
        self._upper = upper
        self._active_handle = "lower"
        self._dragging = False
        self._slider_height = _slider_height()
        self._handle_radius = _handle_radius()
        self._track_height = _track_height()
        self._edge_padding = _edge_padding()
        self._inner_radius = max(2, layout_px(2))
        self._track_brush = QBrush(QColor(COLOR_CARD_ALT))
        self._active_brush = QBrush(QColor(COLOR_ACCENT_SOFT))
        self._handle_brush = QBrush(QColor(COLOR_ACCENT))
        self._handle_pen = QPen(QColor(COLOR_BORDER), 1)
        self._inner_pen = QPen(QColor(COLOR_TEXT), 1)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(self._slider_height)

    def sizeHint(self) -> QSize:
        return QSize(max(180, layout_px(180)), self._slider_height)

    def values(self) -> tuple[int, int]:
        return (self._lower, self._upper)

    def setValues(self, lower: int, upper: int) -> None:
        lower = self._clamp(lower)
        upper = self._clamp(upper)
        if lower > upper:
            lower, upper = upper, lower
        if (lower, upper) == (self._lower, self._upper):
            return
        self._lower = lower
        self._upper = upper
        if self.isVisible():
            self.repaint()
        else:
            self.update()
        self.rangeChanged.emit(self._lower, self._upper)

    def paintEvent(self, _event) -> None:
        if not self.isVisible() or self.width() <= 0 or self.height() <= 0:
            return

        painter = QPainter(self)
        if not painter.isActive():
            return

        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            handle_radius = self._handle_radius
            track_height = self._track_height
            left = handle_radius + self._edge_padding
            right = self.width() - handle_radius - self._edge_padding
            if right <= left:
                return
            center_y = self.height() / 2

            track = QRectF(left, center_y - track_height / 2, right - left, track_height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._track_brush)
            painter.drawRoundedRect(track, track_height / 2, track_height / 2)

            lower_x = self._x_from_value(self._lower)
            upper_x = self._x_from_value(self._upper)
            active = QRectF(lower_x, center_y - track_height / 2, upper_x - lower_x, track_height)
            painter.setBrush(self._active_brush)
            painter.drawRoundedRect(active, track_height / 2, track_height / 2)

            for x in (lower_x, upper_x):
                painter.setPen(self._handle_pen)
                painter.setBrush(self._handle_brush)
                painter.drawEllipse(
                    QRectF(x - handle_radius, center_y - handle_radius, handle_radius * 2, handle_radius * 2)
                )
                painter.setPen(self._inner_pen)
                inner_radius = self._inner_radius
                painter.drawEllipse(
                    QRectF(
                        x - inner_radius,
                        center_y - inner_radius,
                        inner_radius * 2,
                        inner_radius * 2,
                    )
                )
        finally:
            painter.restore()

    def showEvent(self, event) -> None:
        self.setUpdatesEnabled(True)
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self.setUpdatesEnabled(False)
        super().hideEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        lower_distance = abs(event.position().x() - self._x_from_value(self._lower))
        upper_distance = abs(event.position().x() - self._x_from_value(self._upper))
        self._active_handle = "lower" if lower_distance <= upper_distance else "upper"
        self._dragging = True
        self._move_active_handle(event.position().x())

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._move_active_handle(event.position().x())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def keyPressEvent(self, event) -> None:
        if event.key() not in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            super().keyPressEvent(event)
            return
        delta = -1 if event.key() == Qt.Key.Key_Left else 1
        if self._active_handle == "lower":
            self.setValues(min(self._lower + delta, self._upper), self._upper)
        else:
            self.setValues(self._lower, max(self._upper + delta, self._lower))

    def _move_active_handle(self, x: float) -> None:
        value = self._value_from_x(x)
        if self._active_handle == "lower":
            self.setValues(min(value, self._upper), self._upper)
        else:
            self.setValues(self._lower, max(value, self._lower))

    def _clamp(self, value: int) -> int:
        return max(self._minimum, min(self._maximum, int(value)))

    def _x_from_value(self, value: int) -> float:
        handle_radius = self._handle_radius
        left = handle_radius + self._edge_padding
        right = self.width() - handle_radius - self._edge_padding
        if self._maximum == self._minimum:
            return left
        ratio = (value - self._minimum) / (self._maximum - self._minimum)
        return left + ratio * (right - left)

    def _value_from_x(self, x: float) -> int:
        handle_radius = self._handle_radius
        left = handle_radius + self._edge_padding
        right = self.width() - handle_radius - self._edge_padding
        if right <= left:
            return self._minimum
        ratio = max(0.0, min(1.0, (x - left) / (right - left)))
        return round(self._minimum + ratio * (self._maximum - self._minimum))
