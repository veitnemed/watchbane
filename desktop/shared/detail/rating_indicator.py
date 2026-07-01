"""Circular rating indicator widget for detail cards."""

from __future__ import annotations

from desktop.shared.detail.presenters import format_user_score_display
from desktop.shared.detail.profiles import RATING_CIRCLE_DIAMETER, RATING_CIRCLE_WIDGET_SIZE
from desktop.theme import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY,
    FONT_RATING_LABEL_POINT,
    FONT_RATING_VALUE_POINT,
    TRANSPARENT_STYLE,
)


def _score_progress(score) -> float:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, value / 10.0))


def _score_text(score) -> str:
    return format_user_score_display(score)


class RatingCircleIndicator:
    """Small circular score indicator with a radial progress ring."""

    def __new__(
        cls,
        label: str,
        score=None,
        accent: str = COLOR_ACCENT,
        *,
        widget_size: int = RATING_CIRCLE_WIDGET_SIZE,
        circle_diameter: int = RATING_CIRCLE_DIAMETER,
        value_font_point: int = FONT_RATING_VALUE_POINT,
        label_font_point: int = FONT_RATING_LABEL_POINT,
    ):
        from PyQt6.QtWidgets import QWidget

        class _RatingCircleWidget(QWidget):
            def __init__(self, label_text: str, score_value, accent_color: str) -> None:
                super().__init__()
                self._label = label_text
                self._score = score_value
                self._accent = accent_color
                self._widget_size = widget_size
                self._circle_diameter = circle_diameter
                self._value_font_point = value_font_point
                self._label_font_point = label_font_point
                self.setFixedSize(self._widget_size, self._widget_size)
                self.setStyleSheet(TRANSPARENT_STYLE)

            def set_score(self, score_value) -> None:
                self._score = score_value
                self.update()

            def paintEvent(self, _event) -> None:
                from PyQt6.QtCore import QRectF, Qt
                from PyQt6.QtGui import QColor, QFont, QPainter, QPen

                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

                left = (self.width() - self._circle_diameter) / 2
                top = (self.height() - self._circle_diameter) / 2
                rect = QRectF(left, top, self._circle_diameter, self._circle_diameter)
                inner_pad = max(4, int(self._circle_diameter * 0.08))
                inner_rect = rect.adjusted(inner_pad, inner_pad, -inner_pad, -inner_pad)
                ring_pen_width = max(3, int(self._circle_diameter * 0.06))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(COLOR_SURFACE))
                painter.drawEllipse(rect)

                ring_rect = rect.adjusted(ring_pen_width, ring_pen_width, -ring_pen_width, -ring_pen_width)
                track_pen = QPen(QColor(COLOR_BORDER), ring_pen_width)
                track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(track_pen)
                painter.drawArc(ring_rect, 90 * 16, -360 * 16)

                progress = _score_progress(self._score)
                if progress > 0:
                    accent_pen = QPen(QColor(self._accent), ring_pen_width)
                    accent_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    painter.setPen(accent_pen)
                    painter.drawArc(ring_rect, 90 * 16, -int(360 * 16 * progress))

                painter.setPen(QColor(COLOR_TEXT))
                value_font = QFont(FONT_FAMILY)
                value_font.setPointSize(self._value_font_point)
                value_font.setBold(True)
                painter.setFont(value_font)
                value_offset = max(4, int(self._circle_diameter * 0.1))
                painter.drawText(
                    inner_rect.adjusted(0, -value_offset, 0, 0),
                    Qt.AlignmentFlag.AlignCenter,
                    _score_text(self._score),
                )

                painter.setPen(QColor(COLOR_TEXT_SECONDARY))
                label_font = QFont(FONT_FAMILY)
                label_font.setPointSize(self._label_font_point)
                label_font.setBold(True)
                painter.setFont(label_font)
                label_offset = max(18, int(self._circle_diameter * 0.48))
                painter.drawText(
                    inner_rect.adjusted(0, label_offset, 0, -4),
                    Qt.AlignmentFlag.AlignCenter,
                    self._label,
                )

        return _RatingCircleWidget(label, score, accent)
