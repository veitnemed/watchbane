"""Candidate list row delegate (card-style rows with poster thumbnail)."""

from __future__ import annotations

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle

from desktop.candidates.list_model import CandidateListRoles
from desktop.candidates.presenters import format_candidate_metric_value, format_candidate_title_line
from desktop.shared.detail import (
    _elide_text,
    _load_list_thumb_pixmap,
    format_year_display,
)
from desktop.shared.detail import profiles as detail_profiles
from desktop.theme import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_CARD_ALT,
    COLOR_SELECTED_BG,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY,
)


def build_candidate_list_item_delegate(parent, sort_mode: str, data_language: str = "ru"):
    """Card-style list row like Watched: thumbnail, title, year and sort metric."""
    mode = sort_mode
    language = data_language

    class CandidateListItemDelegate(QStyledItemDelegate):
        def sizeHint(self, option, index):
            width = (
                option.rect.width()
                if option.rect.width() > 0
                else detail_profiles.LIST_FALLBACK_WIDTH
            )
            return QSize(width, detail_profiles.LIST_ITEM_HEIGHT)

        def paint(self, painter, option, index) -> None:
            candidate = index.data(Qt.ItemDataRole.UserRole)
            if not isinstance(candidate, dict):
                super().paint(painter, option, index)
                return

            rect = option.rect.adjusted(
                detail_profiles.LIST_ROW_INSET_X,
                detail_profiles.LIST_ROW_INSET_Y,
                -detail_profiles.LIST_ROW_INSET_X,
                -detail_profiles.LIST_ROW_INSET_Y,
            )
            if rect.width() <= 0 or rect.height() <= 0:
                return
            is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
            is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            if is_selected:
                painter.setPen(QPen(QColor(COLOR_ACCENT), 2))
                painter.setBrush(QColor(COLOR_SELECTED_BG))
            elif is_hovered:
                painter.setPen(QPen(QColor(COLOR_BORDER), 1))
                painter.setBrush(QColor(COLOR_CARD_ALT))
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(Qt.BrushStyle.NoBrush)

            if is_selected or is_hovered:
                painter.drawRoundedRect(
                    rect,
                    detail_profiles.LIST_CARD_CORNER_RADIUS,
                    detail_profiles.LIST_CARD_CORNER_RADIUS,
                )

            thumb_left = rect.left() + detail_profiles.LIST_ITEM_H_PADDING
            thumb_top = rect.top() + (rect.height() - detail_profiles.LIST_THUMB_HEIGHT) // 2
            thumb_rect = QRect(
                thumb_left,
                thumb_top,
                detail_profiles.LIST_THUMB_WIDTH,
                detail_profiles.LIST_THUMB_HEIGHT,
            )
            if thumb_rect.width() <= 0 or thumb_rect.height() <= 0:
                painter.restore()
                return

            poster_path = index.data(CandidateListRoles.PosterPathRole)
            thumb = _load_list_thumb_pixmap(poster_path)
            if thumb is not None:
                clip = thumb_rect.adjusted(1, 1, -1, -1)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(COLOR_CARD))
                painter.drawRoundedRect(
                    clip,
                    detail_profiles.LIST_THUMB_CORNER_RADIUS,
                    detail_profiles.LIST_THUMB_CORNER_RADIUS,
                )
                painter.drawPixmap(clip, thumb)
            else:
                painter.setPen(QPen(QColor(COLOR_BORDER), 1))
                painter.setBrush(QColor(COLOR_CARD))
                painter.drawRoundedRect(
                    thumb_rect,
                    detail_profiles.LIST_THUMB_CORNER_RADIUS,
                    detail_profiles.LIST_THUMB_CORNER_RADIUS,
                )
                placeholder_font = QFont(FONT_FAMILY, detail_profiles.LIST_PLACEHOLDER_FONT_POINT)
                painter.setFont(placeholder_font)
                painter.setPen(QPen(QColor(COLOR_TEXT_SECONDARY)))
                painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "—")

            text_left = thumb_rect.right() + detail_profiles.LIST_TEXT_GAP
            text_right = rect.right() - detail_profiles.LIST_ITEM_H_PADDING
            text_width = max(detail_profiles.LIST_MIN_TEXT_WIDTH, text_right - text_left)

            year = candidate.get("year")
            year_text = format_year_display(year)
            metric_text = format_candidate_metric_value(candidate, mode)
            meta_parts = [part for part in (year_text, metric_text if metric_text != "—" else "") if part]
            meta_text = " · ".join(meta_parts)

            title_font = QFont(FONT_FAMILY, detail_profiles.LIST_TITLE_FONT_POINT)
            title_font.setBold(True)
            meta_font = QFont(FONT_FAMILY, detail_profiles.LIST_META_FONT_POINT)

            title_rect = QRect(
                text_left,
                rect.top() + detail_profiles.LIST_ITEM_V_PADDING,
                text_width,
                detail_profiles.LIST_TITLE_BAND_HEIGHT,
            )
            meta_rect = QRect(
                text_left,
                title_rect.bottom(),
                text_width,
                detail_profiles.LIST_META_BAND_HEIGHT,
            )

            painter.setFont(title_font)
            painter.setPen(QPen(QColor(COLOR_TEXT)))
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                _elide_text(
                    painter,
                    format_candidate_title_line(candidate, data_language=language).rsplit(" (", 1)[0],
                    title_rect.width(),
                ),
            )

            if meta_text:
                painter.setFont(meta_font)
                painter.setPen(QPen(QColor(COLOR_ACCENT if is_selected else COLOR_TEXT_SECONDARY)))
                painter.drawText(
                    meta_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    meta_text,
                )

            painter.restore()

    return CandidateListItemDelegate(parent)
