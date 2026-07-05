"""Circular rating and final-star indicators for detail cards."""

from __future__ import annotations

import math

from desktop.shared.detail.presenters import format_user_score_display, normalize_final_score
from desktop.shared.detail.profiles import RATING_CIRCLE_DIAMETER, RATING_CIRCLE_WIDGET_SIZE
from desktop.theme import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_RATING,
    COLOR_STAR_ACTIVE,
    COLOR_STAR_INACTIVE,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY,
    FONT_RATING_LABEL_POINT,
    FONT_RATING_VALUE_POINT,
    TRANSPARENT_STYLE,
    px,
)

STAR_SCALE = 2
STAR_MIN_SIZE = px(16)
STAR_MAX_SIZE = px(22)
STAR_GAP = px(3)
STAR_ROW_RIGHT_OFFSET = px(7)
STAR_EXTRA_WIDTH_PADDING = px(8)


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


def _star_path(center_x: float, center_y: float, outer_radius: float):
    from PyQt6.QtGui import QPainterPath

    inner_radius = outer_radius * 0.48
    path = QPainterPath()
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        radius = outer_radius if index % 2 == 0 else inner_radius
        x = center_x + math.cos(angle) * radius
        y = center_y + math.sin(angle) * radius
        if index == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    return path


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
                self.setFixedSize(self._widget_size, self._widget_size)
                self.setStyleSheet(TRANSPARENT_STYLE)

            def set_score(self, score_value) -> None:
                self._score = score_value
                self._display_value = _score_text(score_value)
                self._ring_progress = _score_progress(score_value)
                self.update()

            def set_payload(
                self,
                *,
                display_value,
                display_label: str,
                ring_progress,
            ) -> None:
                self._display_value = _display_text(display_value)
                self._display_label = display_label
                self._ring_progress = normalize_final_score(ring_progress)
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

        return _RatingCircleWidget(
            label,
            score,
            accent,
            display_score_value=display_value,
            display_label_text=display_label,
            progress_value=ring_progress,
        )


class StarRatingIndicator:
    """Compact 5-star final score indicator drawn outside rating circles."""

    def __new__(cls, *, star_size: int | None = None, star_gap: int | None = None):
        from PyQt6.QtWidgets import QWidget

        class _StarRatingWidget(QWidget):
            def __init__(self) -> None:
                super().__init__()
                self._stars: float | None = None
                self._label: str = ""
                self._custom_star_size = star_size
                self._custom_star_gap = star_gap
                self.setFixedSize(self._resolve_width(), self._resolve_height())
                self.setStyleSheet(TRANSPARENT_STYLE)
                self.hide()

            def _star_size(self) -> int:
                if self._custom_star_size is not None:
                    return max(1, int(self._custom_star_size))
                return max(
                    STAR_MIN_SIZE,
                    min(STAR_MAX_SIZE, int(RATING_CIRCLE_DIAMETER * 0.15 * STAR_SCALE)),
                )

            def _star_gap(self) -> int:
                if self._custom_star_gap is not None:
                    return max(0, int(self._custom_star_gap))
                return STAR_GAP

            def _resolve_width(self) -> int:
                star_size = self._star_size()
                return 5 * star_size + 4 * self._star_gap() + STAR_EXTRA_WIDTH_PADDING

            def _resolve_height(self) -> int:
                return max(self._star_size() + 4, 24)

            def set_stars(self, stars, label: str = "") -> None:
                if stars in (None, ""):
                    self._stars = None
                    self._label = ""
                    self.setToolTip("")
                    self.hide()
                    return
                self._stars = max(0.0, min(5.0, float(stars)))
                self._label = label
                self.setToolTip(label or "")
                self.setFixedSize(self._resolve_width(), self._resolve_height())
                self.show()
                self.update()

            def paintEvent(self, _event) -> None:
                if self._stars is None:
                    return
                from PyQt6.QtCore import QRectF, Qt
                from PyQt6.QtGui import QColor, QPainter, QPen

                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                star_size = self._star_size()
                gap = self._star_gap()
                total_width = 5 * star_size + 4 * gap
                start_x = max(0, (self.width() - total_width) / 2 + STAR_ROW_RIGHT_OFFSET)
                center_y = self.height() / 2
                empty_color = QColor(COLOR_STAR_INACTIVE)
                fill_color = QColor(COLOR_STAR_ACTIVE)

                for index in range(5):
                    x = start_x + index * (star_size + gap)
                    path = _star_path(x + star_size / 2, center_y, star_size / 2)
                    painter.setPen(QPen(empty_color, 1))
                    painter.setBrush(empty_color)
                    painter.drawPath(path)

                    fill_fraction = max(0.0, min(1.0, self._stars - index))
                    if fill_fraction <= 0:
                        continue
                    painter.save()
                    painter.setClipRect(QRectF(x, center_y - star_size / 2, star_size * fill_fraction, star_size))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(fill_color)
                    painter.drawPath(path)
                    painter.restore()

        return _StarRatingWidget()
