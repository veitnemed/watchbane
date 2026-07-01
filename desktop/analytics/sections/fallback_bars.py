"""Fallback bar charts when Plotly/WebEngine is unavailable."""

from __future__ import annotations

import sys

from desktop.analytics.constants import BAR_FILL_STYLE, BAR_HEIGHT, BAR_TRACK_STYLE, BAR_TRACK_WIDTH
from desktop.analytics.sections.common import clear_layout


class AnalyticsFallbackMixin:
    def _points_to_fallback_rows(self, points: list[dict]) -> list[dict]:
        total = sum(int(point.get("count") or 0) for point in points)
        rows: list[dict] = []
        for point in points:
            count = int(point.get("count") or 0)
            percent = point.get("percent")
            if percent is None:
                percent = 0.0 if total == 0 else round(count * 100 / total, 1)
            label = point.get("label")
            if label is None and point.get("score") is not None:
                label = f"{float(point['score']):.1f}"
            rows.append({"label": str(label or ""), "count": count, "percent": float(percent)})
        return rows

    def _fill_distribution_fallback(self, points: list[dict], error: str | None = None) -> None:
        if error is not None:
            self._distribution_layout.addWidget(
                self._make_fallback_message(
                    "Интерактивный график недоступен, показаны упрощённые полосы.\n"
                    f"Python: {sys.executable}\n"
                    f"Ошибка: {error}"
                )
            )

        rows = self._points_to_fallback_rows(points)
        max_count = max((int(row.get("count") or 0) for row in rows), default=0)
        for row in rows:
            self._distribution_layout.addWidget(self._make_bar_row(row, max_count))

    def _fill_genre_count_fallback(self, rows: list[dict], error: str | None = None) -> None:
        if error is not None:
            self._genre_count_layout.addWidget(
                self._make_fallback_message(
                    "Интерактивный график недоступен, показаны упрощённые полосы.\n"
                    f"Python: {sys.executable}\n"
                    f"Ошибка: {error}"
                )
            )

        if not rows:
            self._genre_count_layout.addWidget(
                self._make_list_placeholder("Нет жанров в watched-базе.")
            )
            return

        total = sum(int(row.get("count") or 0) for row in rows)
        fallback_rows = [
            {
                "label": str(row["label"]),
                "count": int(row["count"]),
                "percent": 0.0 if total == 0 else round(int(row["count"]) * 100 / total, 1),
            }
            for row in rows
        ]
        max_count = max((row["count"] for row in fallback_rows), default=0)
        for row in fallback_rows:
            self._genre_count_layout.addWidget(self._make_bar_row(row, max_count))

    def _fill_pool_genre_count_fallback(self, rows: list[dict], error: str | None = None) -> None:
        if error is not None:
            self._pool_genre_count_layout.addWidget(
                self._make_fallback_message(
                    "Интерактивный график недоступен, показаны упрощённые полосы.\n"
                    f"Python: {sys.executable}\n"
                    f"Ошибка: {error}"
                )
            )

        if not rows:
            self._pool_genre_count_layout.addWidget(
                self._make_list_placeholder("Нет жанров в candidate pool.")
            )
            return

        total = sum(int(row.get("count") or 0) for row in rows)
        fallback_rows = [
            {
                "label": str(row["label"]),
                "count": int(row["count"]),
                "percent": 0.0 if total == 0 else round(int(row["count"]) * 100 / total, 1),
            }
            for row in rows
        ]
        max_count = max((row["count"] for row in fallback_rows), default=0)
        for row in fallback_rows:
            self._pool_genre_count_layout.addWidget(self._make_bar_row(row, max_count))

    def _fill_year_average_fallback(self, points: list[dict], error: str | None = None) -> None:
        if error is not None:
            self._year_average_layout.addWidget(
                self._make_fallback_message(
                    "Интерактивный график недоступен, показаны упрощённые строки.\n"
                    f"Python: {sys.executable}\n"
                    f"Ошибка: {error}"
                )
            )

        if not points:
            self._year_average_layout.addWidget(
                self._make_list_placeholder("Нет данных по годам выхода.")
            )
            return

        for point in points:
            year = int(point["year"])
            average = float(point["average"])
            count = int(point["count"])
            self._year_average_layout.addWidget(
                self._make_insight_line(f"{year} · средняя {average:.1f} · {count} тайтлов")
            )

    def _make_fallback_message(self, text: str):
        from PyQt6.QtWidgets import QLabel

        label = QLabel(text)
        label.setObjectName("analyticsFallback")
        label.setWordWrap(True)
        return label

    def _make_bar_row(self, item: dict, max_count: int):
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

        row = QWidget()
        row.setObjectName("analyticsBarRow")
        row.setFixedHeight(24)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(item["label"])
        label.setObjectName("barLabel")
        label.setFixedWidth(76)
        layout.addWidget(label)

        track = QFrame()
        track.setObjectName("barTrack")
        track.setStyleSheet(BAR_TRACK_STYLE)
        track.setFixedHeight(BAR_HEIGHT)
        track.setFixedWidth(BAR_TRACK_WIDTH)
        track_layout = QHBoxLayout(track)
        track_layout.setContentsMargins(0, 0, 0, 0)
        track_layout.setSpacing(0)
        fill = QFrame()
        fill.setObjectName("barFill")
        fill.setStyleSheet(BAR_FILL_STYLE)
        fill.setFixedHeight(BAR_HEIGHT)
        fill_width = (
            0
            if max_count == 0 or item["count"] == 0
            else max(8, int(BAR_TRACK_WIDTH * item["count"] / max_count))
        )
        fill.setFixedWidth(fill_width)
        track_layout.addWidget(fill)
        track_layout.addStretch()
        layout.addWidget(track)

        count = QLabel(f"{item['count']} · {item['percent']:.1f}%")
        count.setObjectName("barCount")
        count.setFixedWidth(92)
        layout.addWidget(count)
        layout.addStretch()
        return row

    def _make_list_placeholder(self, text: str):
        from PyQt6.QtWidgets import QLabel

        label = QLabel(text)
        label.setObjectName("insightText")
        label.setWordWrap(True)
        return label

    def _make_list_extra(self, text: str):
        from PyQt6.QtWidgets import QLabel

        label = QLabel(text)
        label.setObjectName("completenessSubline")
        return label
