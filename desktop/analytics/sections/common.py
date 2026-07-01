"""Shared analytics UI helpers and section chrome."""

from __future__ import annotations

from desktop.analytics.constants import (
    ANALYTICS_SECTION_PADDING,
    ANALYTICS_SECTION_SPACING,
    SECTION_HEADER_ICON_BADGE_SIZE,
)


def format_metric(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.1f}"


def entries_to_records(entries: list[tuple[str, dict, dict]]) -> dict:
    return {key: movie for key, movie, _card in entries}


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        if child_layout is not None:
            clear_layout(child_layout)
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


class AnalyticsSectionUIMixin:
    """Section headers, insight rows and framed sections."""

    def _make_section(
        self,
        title_text: str,
        content_layout,
        icon_text: str = "",
        *,
        prefix_widgets=None,
        show_menu_stub: bool = False,
    ):
        from PyQt6.QtWidgets import QFrame, QVBoxLayout

        frame = QFrame()
        frame.setObjectName("analyticsSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            ANALYTICS_SECTION_PADDING,
            ANALYTICS_SECTION_PADDING,
            ANALYTICS_SECTION_PADDING,
            ANALYTICS_SECTION_PADDING,
        )
        layout.setSpacing(ANALYTICS_SECTION_SPACING)

        layout.addWidget(
            self._make_section_header(title_text, icon_text, show_menu_stub=show_menu_stub)
        )
        if prefix_widgets:
            for widget in prefix_widgets:
                layout.addWidget(widget)
        layout.addLayout(content_layout)
        return frame

    def _make_section_header(self, title_text: str, icon_text: str, *, show_menu_stub: bool = False):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

        header = QWidget()
        header.setObjectName("sectionHeader")
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        icon_badge = QFrame()
        icon_badge.setObjectName("sectionHeaderIconBadge")
        icon_badge.setFixedSize(
            SECTION_HEADER_ICON_BADGE_SIZE,
            SECTION_HEADER_ICON_BADGE_SIZE,
        )
        icon_layout = QVBoxLayout(icon_badge)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon = QLabel(icon_text)
        icon.setObjectName("sectionHeaderIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon)

        title = QLabel(title_text)
        title.setObjectName("sectionTitle")

        row.addWidget(icon_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(title, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addStretch()
        if show_menu_stub:
            menu = QLabel("⋮")
            menu.setObjectName("sectionHeaderMenu")
            row.addWidget(menu, alignment=Qt.AlignmentFlag.AlignVCenter)
        return header

    def _make_insight_line(self, text: str):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

        row = QWidget()
        row.setObjectName("insightRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        bullet = QLabel("●")
        bullet.setObjectName("insightBullet")
        bullet.setFixedWidth(12)
        bullet.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        label = QLabel(text)
        label.setObjectName("insightText")
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        layout.addWidget(bullet, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(label, stretch=1)
        return row
