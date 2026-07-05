"""List item delegate and thumbnail helpers for watched-style rows."""

from __future__ import annotations

from desktop.shared.detail import profiles as detail_profiles
from desktop.shared.detail.posters import resolve_local_poster_path
from desktop.shared.detail.presenters import format_user_score_display, format_year_display
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
from desktop.theme.scaling import list_px

_thumb_pixmap_cache: dict[str, object] = {}


def fit_poster_pixmap_for_display(pixmap, max_width: int, max_height: int):
    """Fit a poster into the display box without unnecessary upscale blur."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap

    if pixmap.isNull():
        return pixmap
    source_size = pixmap.size()
    if source_size.isEmpty():
        return pixmap

    target_size = source_size.scaled(max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio)
    if target_size.isEmpty():
        return pixmap

    needs_downscale = target_size.width() < source_size.width() or target_size.height() < source_size.height()
    if not needs_downscale:
        return pixmap

    return pixmap.scaled(
        target_size.width(),
        target_size.height(),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _load_list_thumb_pixmap(poster_path: str | None):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap

    if poster_path is None:
        return None
    cached = _thumb_pixmap_cache.get(poster_path)
    if cached is not None:
        return cached if cached is not False else None
    pixmap = QPixmap(poster_path)
    if pixmap.isNull():
        _thumb_pixmap_cache[poster_path] = False
        return None
    scaled = pixmap.scaled(
        detail_profiles.LIST_THUMB_WIDTH,
        detail_profiles.LIST_THUMB_HEIGHT,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    _thumb_pixmap_cache[poster_path] = scaled
    return scaled


def _elide_text(painter, text: str, max_width: int) -> str:
    from PyQt6.QtCore import Qt

    metrics = painter.fontMetrics()
    return metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(list_px(20), max_width))


class WatchedListItemDelegate:
    """Rich list row: thumbnail, title, year and user score."""

    def __new__(cls, parent=None):
        from PyQt6.QtCore import QRect, QSize, Qt
        from PyQt6.QtGui import QColor, QFont, QPainter, QPen
        from PyQt6.QtWidgets import QStyledItemDelegate, QStyle

        class _WatchedListItemDelegate(QStyledItemDelegate):
            def sizeHint(self, option, index):
                width = (
                    option.rect.width()
                    if option.rect.width() > 0
                    else detail_profiles.LIST_FALLBACK_WIDTH
                )
                return QSize(width, detail_profiles.LIST_ITEM_HEIGHT)

            def paint(self, painter, option, index) -> None:
                entry = index.data(Qt.ItemDataRole.UserRole)
                if not isinstance(entry, tuple) or len(entry) != 3:
                    super().paint(painter, option, index)
                    return

                _key, movie, card = entry
                rect = option.rect.adjusted(
                    detail_profiles.LIST_ROW_INSET_X,
                    detail_profiles.LIST_ROW_INSET_Y,
                    -detail_profiles.LIST_ROW_INSET_X,
                    -detail_profiles.LIST_ROW_INSET_Y,
                )
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

                poster_path = resolve_local_poster_path(movie, card)
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
                    painter.setPen(QColor(COLOR_TEXT_SECONDARY))
                    painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "—")

                text_left = thumb_rect.right() + detail_profiles.LIST_TEXT_GAP
                text_right = rect.right() - detail_profiles.LIST_ITEM_H_PADDING
                text_width = max(detail_profiles.LIST_MIN_TEXT_WIDTH, text_right - text_left)

                title = str(card.get("title") or _key or "Без названия")
                year = card.get("year")
                year_text = format_year_display(year)
                score_text = format_user_score_display(card.get("user_score"))
                meta_parts = [part for part in (year_text, score_text if score_text != "—" else "") if part]
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
                painter.setPen(QColor(COLOR_TEXT if is_selected else COLOR_TEXT))
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

        return _WatchedListItemDelegate(parent)
