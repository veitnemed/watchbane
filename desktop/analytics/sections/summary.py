"""KPI cards, dataset completeness and insight bullets."""

from __future__ import annotations

from dataset.score_analytics import summarize_dataset_completeness

from desktop.analytics.constants import (
    ANALYTICS_SUMMARY_CARD_PADDING,
    ANALYTICS_SUMMARY_CARD_SPACING,
    SUMMARY_CARD_HEIGHT,
    SUMMARY_CARD_ICONS,
    SUMMARY_ICON_BADGE_SIZE,
)
from desktop.analytics.sections.common import clear_layout, format_metric


class AnalyticsSummaryMixin:
    def _fill_summary(self, summary: dict) -> None:
        clear_layout(self._summary_layout)
        items = (
            ("Всего", summary["count"]),
            ("Средняя", summary["average"]),
            ("Медиана", summary["median"]),
            ("Минимум", summary["minimum"]),
            ("Максимум", summary["maximum"]),
        )
        for label, value in items:
            icon = SUMMARY_CARD_ICONS.get(label, "•")
            self._summary_layout.addWidget(
                self._make_summary_card(label, format_metric(value), icon),
                stretch=1,
            )

    def _make_summary_card(self, label_text: str, value_text: str, icon_text: str):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

        frame = QFrame()
        frame.setObjectName("summaryCard")
        frame.setFixedHeight(SUMMARY_CARD_HEIGHT)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(
            ANALYTICS_SUMMARY_CARD_PADDING,
            ANALYTICS_SUMMARY_CARD_PADDING,
            ANALYTICS_SUMMARY_CARD_PADDING,
            ANALYTICS_SUMMARY_CARD_PADDING,
        )
        layout.setSpacing(10)

        icon_badge = QFrame()
        icon_badge.setObjectName("summaryIconBadge")
        icon_badge.setFixedSize(SUMMARY_ICON_BADGE_SIZE, SUMMARY_ICON_BADGE_SIZE)
        badge_layout = QVBoxLayout(icon_badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        icon = QLabel(icon_text)
        icon.setObjectName("summaryIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(icon)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(ANALYTICS_SUMMARY_CARD_SPACING)

        label = QLabel(label_text)
        label.setObjectName("summaryLabel")
        value = QLabel(value_text)
        value.setObjectName("summaryValue")
        text_column.addWidget(label)
        text_column.addWidget(value)
        text_column.addStretch()

        layout.addWidget(icon_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(text_column, stretch=1)
        return frame

    def _fill_completeness(self, completeness: dict) -> None:
        summary = summarize_dataset_completeness(completeness)
        self._completeness_headline.setText(summary["headline_text"])
        self._completeness_subline.setText(summary["subline_text"])

    def _fill_insights(self, insights: list[str]) -> None:
        clear_layout(self._insights_layout)
        for text in insights:
            self._insights_layout.addWidget(self._make_insight_line(text))
