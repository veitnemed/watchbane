"""Circular rating indicator widget for detail cards."""

from __future__ import annotations

from desktop.shared.detail.presenters import format_user_score_display, normalize_final_score
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


def _display_text(value) -> str:
    if value in (None, ""):
        return "—"
    return str(value)


class RatingCircleIndicator:
    """Small circular score indicator with a radial progress ring."""

    def __new__(
        cls,
        label: str,
        score=None,
        accent: str = COLOR_ACCENT,
        *,
        display_value=None,
        display_label: str | None = None,
        ring_progress=None,
        footer_label: str | None = None,
        widget_size: int = RATING_CIRCLE_WIDGET_SIZE,
        circle_diameter: int = RATING_CIRCLE_DIAMETER,
        value_font_point: int = FONT_RATING_VALUE_POINT,
        label_font_point: int = FONT_RATING_LABEL_POINT,
    ):
        from PyQt6.QtWidgets import QWidget

        class _RatingCircleWidget(QWidget):
            def __init__(
                self,
                label_text: str,
                score_value,
                accent_color: str,
                *,
                display_score_value,
                display_label_text: str | None,
                progress_value,
                footer_text: str | None,
            ) -> None:
                super().__init__()
                self._label = label_text
                self._score = score_value
                self._accent = accent_color
                self._widget_size = widget_size
                self._circle_diameter = circle_diameter
                self._value_font_point = value_font_point
                self._label_font_point = label_font_point
                self._display_value = _display_text(
                    score_value if display_score_value is None else display_score_value
                )
                self._display_label = display_label_text or label_text
                self._ring_progress = (
                    _score_progress(score_value)
                    if progress_value is None
                    else normalize_final_score(progress_value)
                )
                self._footer_label = footer_text
                self._footer_height = 20 if self._footer_label else 0
                self.setFixedSize(self._widget_size, self._widget_size + self._footer_height)
                self.setStyleSheet(TRANSPARENT_STYLE)

            def set_score(self, score_value) -> None:
                self._score = score_value
                self._display_value = _score_text(score_value)
                self._ring_progress = _score_progress(score_value)
                self._footer_label = None
                self._footer_height = 0
                self.setFixedSize(self._widget_size, self._widget_size)
                self.update()

            def set_payload(
                self,
                *,
                display_value,
                display_label: str,
                ring_progress,
                footer_label: str | None = None,
            ) -> None:
                self._display_value = _display_text(display_value)
                self._display_label = display_label
                self._ring_progress = normalize_final_score(ring_progress)
                self._footer_label = footer_label
                self._footer_height = 20 if self._footer_label else 0
                self.setFixedSize(self._widget_size, self._widget_size + self._footer_height)
                self.update()

            def paintEvent(self, _event) -> None:
                from PyQt6.QtCore import QRectF, Qt
                from PyQt6.QtGui import QColor, QFont, QPainter, QPen

                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

                circle_area_height = self.height() - self._footer_height
                left = (self.width() - self._circle_diameter) / 2
                top = (circle_area_height - self._circle_diameter) / 2
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

                progress = max(0.0, min(1.0, self._ring_progress))
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
                    self._display_value,
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
                    self._display_label,
                )

                if self._footer_label:
                    painter.setPen(QColor(COLOR_TEXT_SECONDARY))
                    footer_font = QFont(FONT_FAMILY)
                    footer_font.setPointSize(max(7, self._label_font_point))
                    footer_font.setBold(True)
                    painter.setFont(footer_font)
                    footer_rect = QRectF(0, circle_area_height - 1, self.width(), self._footer_height)
                    painter.drawText(
                        footer_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        self._footer_label,
                    )

        return _RatingCircleWidget(
            label,
            score,
            accent,
            display_score_value=display_value,
            display_label_text=display_label,
            progress_value=ring_progress,
            footer_text=footer_label,
        )
