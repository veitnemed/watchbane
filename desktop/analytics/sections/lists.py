"""Text list sections: rating gaps, suspicious and dense scores."""

from __future__ import annotations

from dataset import service

from desktop.analytics.constants import (
    ANALYTICS_DENSE_ROW_PADDING_X,
    ANALYTICS_DENSE_ROW_PADDING_Y,
    ANALYTICS_DENSE_ROW_SPACING,
    ANALYTICS_DENSE_TEXT_SPACING,
    DENSE_SCORE_BADGE_SIZE,
)
from desktop.analytics.sections.common import clear_layout, format_metric


class AnalyticsListsMixin:
    def _make_list_expand_button(self, text: str, handler):
        from PyQt6.QtWidgets import QPushButton

        button = QPushButton(text)
        button.setObjectName("analyticsListExpand")
        button.setFlat(True)
        button.clicked.connect(handler)
        return button

    def _fill_rating_higher(self, rows: list[dict], extra_count: int) -> None:
        self._fill_text_list(
            self._rating_higher_layout,
            [service.format_rating_gap_line(row) for row in rows],
            empty_text="Нет тайтлов, где ваша оценка сильно выше IMDb.",
            extra_count=extra_count,
        )

    def _fill_rating_lower(self, rows: list[dict], extra_count: int) -> None:
        self._fill_text_list(
            self._rating_lower_layout,
            [service.format_rating_gap_line(row) for row in rows],
            empty_text="Нет тайтлов, где ваша оценка сильно ниже IMDb.",
            extra_count=extra_count,
        )

    def _fill_suspicious(self, rows: list[dict], extra_count: int) -> None:
        self._fill_text_list(
            self._suspicious_layout,
            [service.format_suspicious_rating_line(row) for row in rows],
            empty_text="Подозрительных оценок не найдено.",
            extra_count=extra_count,
        )

    def _fill_text_list(
        self,
        layout,
        lines: list[str],
        *,
        empty_text: str,
        extra_count: int = 0,
    ) -> None:
        clear_layout(layout)
        if not lines:
            layout.addWidget(self._make_list_placeholder(empty_text))
            return
        for line in lines:
            layout.addWidget(self._make_insight_line(line))
        if extra_count > 0:
            layout.addWidget(self._make_list_extra(f"ещё {extra_count}"))

    def _fill_dense_scores(self, dense_scores: list[dict]) -> None:
        clear_layout(self._dense_layout)
        if len(dense_scores) == 0:
            self._dense_layout.addWidget(
                self._make_dense_row({"score": None, "count": 0, "titles": [], "extra_count": 0})
            )
            return
        for row in dense_scores:
            self._dense_layout.addWidget(self._make_dense_row(row))

    def _make_dense_score_badge(self, score_text: str):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

        badge = QFrame()
        badge.setObjectName("denseScoreBadge")
        badge.setFixedSize(DENSE_SCORE_BADGE_SIZE, DENSE_SCORE_BADGE_SIZE)
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)

        score = QLabel(score_text)
        score.setObjectName("denseScore")
        score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.addWidget(score)
        return badge

    def _make_dense_row(self, dense_row: dict):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

        row = QFrame()
        row.setObjectName("sameScoreCard")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(
            ANALYTICS_DENSE_ROW_PADDING_X,
            ANALYTICS_DENSE_ROW_PADDING_Y,
            ANALYTICS_DENSE_ROW_PADDING_X,
            ANALYTICS_DENSE_ROW_PADDING_Y,
        )
        layout.setSpacing(ANALYTICS_DENSE_ROW_SPACING)

        score_text = "-" if dense_row.get("score") is None else format_metric(dense_row["score"])
        count_text = "Нет оценок" if dense_row.get("count", 0) == 0 else f"{dense_row['count']} тайтлов"
        titles = dense_row.get("titles", [])
        extra_count = dense_row.get("extra_count", 0)
        if titles:
            titles_text = " · ".join(titles)
            if extra_count > 0:
                titles_text = f"{titles_text} · ещё {extra_count}"
        else:
            titles_text = "Нет тайтлов для отображения"

        layout.addWidget(self._make_dense_score_badge(score_text), alignment=Qt.AlignmentFlag.AlignVCenter)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(ANALYTICS_DENSE_TEXT_SPACING)
        count = QLabel(count_text)
        count.setObjectName("denseCount")
        title_label = QLabel(titles_text)
        title_label.setObjectName("sameScoreTitles")
        title_label.setWordWrap(True)
        text_column.addWidget(count)
        text_column.addWidget(title_label)
        layout.addLayout(text_column, stretch=1)
        return row
