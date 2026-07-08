"""Small painted icons for title detail-card action buttons."""

from __future__ import annotations


def make_detail_action_icon(kind: str, color: str, disabled_color: str | None = None):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

    icon = QIcon()
    for mode, item_color in (
        (QIcon.Mode.Normal, color),
        (QIcon.Mode.Disabled, disabled_color or color),
    ):
        pixmap = QPixmap(28, 28)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen()
        pen.setColor(Qt.GlobalColor.transparent)
        painter.setPen(pen)

        draw_pen = QPen()
        draw_pen.setColor(QColor(item_color))
        draw_pen.setWidthF(2.0)
        draw_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        draw_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(draw_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if kind == "eye":
            path = QPainterPath()
            path.moveTo(4, 14)
            path.cubicTo(8, 7, 20, 7, 24, 14)
            path.cubicTo(20, 21, 8, 21, 4, 14)
            painter.drawPath(path)
            painter.drawEllipse(10, 10, 8, 8)
            painter.setBrush(QColor(item_color))
            painter.drawEllipse(13, 13, 2, 2)
        elif kind == "hide":
            painter.drawEllipse(6, 6, 16, 16)
            painter.drawLine(9, 19, 19, 9)

        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon


def make_detail_metadata_pixmap(kind: str, color: str, size: int = 20):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.2, size / 13))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    pad = max(2, int(size * 0.16))
    mid = size // 2
    if kind == "type":
        painter.drawRoundedRect(pad, pad + 2, size - 2 * pad, size - 2 * pad - 2, 2, 2)
        painter.drawLine(pad + 2, pad + 6, size - pad - 2, pad + 6)
    elif kind == "country":
        painter.drawEllipse(pad, pad, size - 2 * pad, size - 2 * pad)
        painter.drawLine(mid, pad, mid, size - pad)
        painter.drawArc(pad + 3, pad, size - 2 * pad - 6, size - 2 * pad, 90 * 16, 180 * 16)
        painter.drawArc(pad + 3, pad, size - 2 * pad - 6, size - 2 * pad, -90 * 16, 180 * 16)
    elif kind == "watch":
        painter.drawRoundedRect(pad, pad + 2, size - 2 * pad, size - 2 * pad - 4, 2, 2)
        painter.drawLine(mid, size - pad - 2, mid, size - pad + 1)
        painter.drawLine(mid - 4, size - pad + 1, mid + 4, size - pad + 1)
    elif kind == "votes":
        painter.drawLine(pad, size - pad, size - pad, size - pad)
        painter.drawLine(pad + 2, size - pad, pad + 2, mid)
        painter.drawLine(mid, size - pad, mid, pad + 3)
        painter.drawLine(size - pad - 2, size - pad, size - pad - 2, pad + 8)
    elif kind == "date":
        painter.drawRoundedRect(pad, pad + 2, size - 2 * pad, size - 2 * pad - 2, 2, 2)
        painter.drawLine(pad, pad + 7, size - pad, pad + 7)
        painter.drawLine(pad + 4, pad, pad + 4, pad + 4)
        painter.drawLine(size - pad - 4, pad, size - pad - 4, pad + 4)
    else:
        painter.drawEllipse(pad, pad, size - 2 * pad, size - 2 * pad)
        painter.drawPoint(int(mid), int(mid - 3))
        painter.drawLine(mid, mid + 1, mid, size - pad - 3)

    painter.end()
    return pixmap
