"""Accessible discrete rotary control for recommendation-vector levels."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QPainter, QPen
from PyQt6.QtWidgets import QDial, QMenu

from desktop.theme.scaling import control_px, font_px
from desktop.theme.tokens import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_BORDER_HOVER,
    COLOR_CARD,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
)


class SteppedRotaryControl(QDial):
    """QDial with a deterministic 270-degree arc and canonical text readout."""

    canonicalTextChanged = pyqtSignal(str)

    def __init__(
        self,
        labels: tuple[str, ...] | list[str],
        *,
        value: int = 0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._labels = tuple(str(label) for label in labels)
        if not self._labels:
            raise ValueError("SteppedRotaryControl requires at least one label")
        self.setRange(0, len(self._labels) - 1)
        self.setSingleStep(1)
        self.setPageStep(1)
        self.setWrapping(False)
        self.setNotchesVisible(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setValue(max(0, min(self.maximum(), int(value))))
        self.valueChanged.connect(self._on_value_changed)

    def sizeHint(self) -> QSize:
        return QSize(control_px(132), control_px(150))

    def minimumSizeHint(self) -> QSize:
        return QSize(control_px(112), control_px(132))

    def canonical_text(self) -> str:
        return self._labels[self.value()]

    def set_labels(self, labels: tuple[str, ...] | list[str]) -> None:
        current = self.value()
        self._labels = tuple(str(label) for label in labels)
        if not self._labels:
            raise ValueError("SteppedRotaryControl requires at least one label")
        self.setRange(0, len(self._labels) - 1)
        self.setValue(min(current, self.maximum()))
        self.update()

    def _on_value_changed(self, _value: int) -> None:
        self.canonicalTextChanged.emit(self.canonical_text())
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Home:
            self.setValue(self.minimum())
            event.accept()
            return
        if event.key() == Qt.Key.Key_End:
            self.setValue(self.maximum())
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        center = self.rect().center()
        radius = min(self.width(), self.height() - control_px(36)) * 0.25
        if event.button() == Qt.MouseButton.LeftButton and (
            (event.position().x() - center.x()) ** 2
            + (event.position().y() - center.y()) ** 2
            <= radius ** 2
        ):
            menu = QMenu(self)
            for index, label in enumerate(self._labels):
                action = menu.addAction(label)
                action.setCheckable(True)
                action.setChecked(index == self.value())
                action.triggered.connect(lambda _checked=False, value=index: self.setValue(value))
            menu.exec(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        width = self.width()
        dial_size = min(width - control_px(18), self.height() - control_px(42))
        dial_size = max(control_px(64), dial_size)
        rect = QRectF(
            (width - dial_size) / 2,
            control_px(5),
            dial_size,
            dial_size,
        )
        center = rect.center()
        radius = rect.width() / 2 - control_px(8)
        start_degrees = 225.0
        sweep_degrees = 270.0
        steps = max(1, self.maximum() - self.minimum())
        ratio = (self.value() - self.minimum()) / steps

        painter.setPen(QPen(QColor(COLOR_BORDER_HOVER), control_px(4), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, int(-start_degrees * 16), int(sweep_degrees * 16))
        painter.setPen(QPen(QColor(COLOR_ACCENT), control_px(4), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, int(-start_degrees * 16), int(sweep_degrees * ratio * 16))

        for index in range(self.maximum() + 1):
            tick_ratio = index / steps
            angle = math.radians(start_degrees - sweep_degrees * tick_ratio)
            outer = QPointF(
                center.x() + math.cos(angle) * (radius + control_px(4)),
                center.y() - math.sin(angle) * (radius + control_px(4)),
            )
            inner = QPointF(
                center.x() + math.cos(angle) * (radius - control_px(3)),
                center.y() - math.sin(angle) * (radius - control_px(3)),
            )
            painter.setPen(QPen(QColor(COLOR_ACCENT_HOVER if index <= self.value() else COLOR_TEXT_MUTED), control_px(2)))
            painter.drawLine(inner, outer)

        painter.setPen(QPen(QColor(COLOR_BORDER_HOVER), control_px(1)))
        painter.setBrush(QColor(COLOR_CARD))
        knob = QRectF(center.x() - radius * 0.64, center.y() - radius * 0.64, radius * 1.28, radius * 1.28)
        painter.drawEllipse(knob)

        angle = math.radians(start_degrees - sweep_degrees * ratio)
        marker = QPointF(
            center.x() + math.cos(angle) * radius * 0.45,
            center.y() - math.sin(angle) * radius * 0.45,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLOR_ACCENT_HOVER))
        painter.drawEllipse(marker, control_px(4), control_px(4))

        font = painter.font()
        font.setPixelSize(font_px(14))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(COLOR_TEXT))
        text_rect = QRectF(0, rect.bottom() + control_px(4), width, control_px(30))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.canonical_text())

        if self.hasFocus():
            painter.setPen(QPen(QColor(COLOR_ACCENT_HOVER), control_px(1), Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), control_px(6), control_px(6))
