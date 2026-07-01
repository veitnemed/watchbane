"""Candidate list row delegate (card-style rows with poster thumbnail)."""

from __future__ import annotations

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle

from desktop.candidates.presenters import (
    format_candidate_metric_value,
    resolve_local_poster_path_for_candidate,
)
from desktop.shared.detail import (
    LIST_ITEM_HEIGHT,
    LIST_ITEM_H_PADDING,
    LIST_ITEM_V_PADDING,
    LIST_TEXT_GAP,
    LIST_THUMB_HEIGHT,
    LIST_THUMB_WIDTH,
    _elide_text,
    _load_list_thumb_pixmap,
)
from desktop.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_SOFT,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_CARD_ALT,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY,
)


def build_candidate_list_item_delegate(parent, sort_mode: str):
    """Card-style list row like Watched: thumbnail, title, year and sort metric."""
    mode = sort_mode

    class CandidateListItemDelegate(QStyledItemDelegate):
        def sizeHint(self, option, index):
            width = option.rect.width() if option.rect.width() > 0 else 280
            return QSize(width, LIST_ITEM_HEIGHT)

        def paint(self, painter, option, index) -> None:
            candidate = index.data(Qt.ItemDataRole.UserRole)
            if not isinstance(candidate, dict):
                super().paint(painter, option, index)
                return

            rect = option.rect.adjusted(2, 1, -2, -1)
            is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
            is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            if is_selected:
                painter.setPen(QPen(QColor(COLOR_ACCENT), 2))
                painter.setBrush(QColor(COLOR_ACCENT_SOFT))
            elif is_hovered:
                painter.setPen(QPen(QColor(COLOR_BORDER), 1))
                painter.setBrush(QColor(COLOR_CARD_ALT))
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(Qt.BrushStyle.NoBrush)

            if is_selected or is_hovered:
                painter.drawRoundedRect(rect, 10, 10)

            thumb_left = rect.left() + LIST_ITEM_H_PADDING
            thumb_top = rect.top() + (rect.height() - LIST_THUMB_HEIGHT) // 2
            thumb_rect = QRect(thumb_left, thumb_top, LIST_THUMB_WIDTH, LIST_THUMB_HEIGHT)

            poster_path = resolve_local_poster_path_for_candidate(candidate)
            thumb = _load_list_thumb_pixmap(poster_path)
            if thumb is not None:
                clip = thumb_rect.adjusted(1, 1, -1, -1)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(COLOR_CARD))
                painter.drawRoundedRect(clip, 6, 6)
                painter.drawPixmap(clip, thumb)
            else:
                painter.setPen(QPen(QColor(COLOR_BORDER), 1))
                painter.setBrush(QColor(COLOR_CARD))
                painter.drawRoundedRect(thumb_rect, 6, 6)
                placeholder_font = QFont(FONT_FAMILY, 8)
                painter.setFont(placeholder_font)
                painter.setPen(QColor(COLOR_TEXT_SECONDARY))
                painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "—")

            text_left = thumb_rect.right() + LIST_TEXT_GAP
            text_right = rect.right() - LIST_ITEM_H_PADDING
            text_width = max(40, text_right - text_left)

            title = str(candidate.get("title") or candidate.get("name") or "Без названия")
            year = candidate.get("year")
            year_text = str(year) if year not in (None, "") else ""
            metric_text = format_candidate_metric_value(candidate, mode)
            meta_parts = [part for part in (year_text, metric_text if metric_text != "—" else "") if part]
            meta_text = " · ".join(meta_parts)

            title_font = QFont(FONT_FAMILY)
            title_font.setPointSize(10)
            title_font.setBold(True)
            meta_font = QFont(FONT_FAMILY)
            meta_font.setPointSize(9)

            title_rect = QRect(text_left, rect.top() + LIST_ITEM_V_PADDING, text_width, 28)
            meta_rect = QRect(text_left, title_rect.bottom(), text_width, 20)

            painter.setFont(title_font)
            painter.setPen(QColor(COLOR_TEXT))
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                _elide_text(painter, title, title_rect.width()),
            )

            if meta_text:
                painter.setFont(meta_font)
                painter.setPen(QColor(COLOR_ACCENT if is_selected else COLOR_TEXT_SECONDARY))
                painter.drawText(
                    meta_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    meta_text,
                )

            painter.restore()

    return CandidateListItemDelegate(parent)
