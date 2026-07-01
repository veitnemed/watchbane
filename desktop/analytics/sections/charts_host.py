"""Plotly chart host and distribution/genre/year chart fill helpers."""

from __future__ import annotations

import os
import tempfile

from desktop.analytics.constants import ANALYTICS_PLOTLY_BASE_HEIGHT, ANALYTICS_PLOTLY_OBJECT_NAME
from desktop.analytics.sections.common import clear_layout


class AnalyticsChartsMixin:
    def _clear_plotly_html_files(self) -> None:
        while self._plotly_html_paths:
            path = self._plotly_html_paths.pop()
            try:
                os.remove(path)
            except OSError:
                pass

    def _write_plotly_html_file(self, html: str) -> str:
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".html",
            prefix="recommended_plotly_",
            delete=False,
        )
        with handle:
            handle.write(html)
        self._plotly_html_paths.append(handle.name)
        return handle.name

    def _fill_plotly_chart(
        self,
        layout,
        data,
        *,
        build_html,
        chart_height: int,
        fallback,
    ) -> None:
        clear_layout(layout)

        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtWebEngineWidgets import QWebEngineView
        except ImportError as error:
            fallback(data, str(error))
            return

        try:
            html = build_html(data)
        except ImportError as error:
            fallback(data, str(error))
            return

        try:
            from PyQt6.QtWidgets import QSizePolicy

            view = QWebEngineView()
            view.setObjectName(ANALYTICS_PLOTLY_OBJECT_NAME)
            view.setFixedHeight(chart_height)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            html_path = self._write_plotly_html_file(html)
            view.setUrl(QUrl.fromLocalFile(html_path))
            layout.addWidget(view)
        except Exception as error:
            fallback(data, str(error))

    def _fill_distribution(self, points: list[dict]) -> None:
        from desktop.analytics.charts import build_score_count_html

        self._fill_plotly_chart(
            self._distribution_layout,
            points,
            build_html=build_score_count_html,
            chart_height=ANALYTICS_PLOTLY_BASE_HEIGHT,
            fallback=self._fill_distribution_fallback,
        )

    def _fill_genre_count(self, rows: list[dict]) -> None:
        from desktop.analytics.charts import bar_chart_height, build_genre_count_html

        height = bar_chart_height(len(rows))
        self._fill_plotly_chart(
            self._genre_count_layout,
            rows,
            build_html=build_genre_count_html,
            chart_height=height,
            fallback=self._fill_genre_count_fallback,
        )

    def _fill_pool_genre_count(self, rows: list[dict]) -> None:
        from desktop.analytics.charts import bar_chart_height, build_genre_count_html

        height = bar_chart_height(len(rows))
        self._fill_plotly_chart(
            self._pool_genre_count_layout,
            rows,
            build_html=build_genre_count_html,
            chart_height=height,
            fallback=self._fill_pool_genre_count_fallback,
        )

    def _fill_year_average(self, points: list[dict]) -> None:
        from desktop.analytics.charts import build_year_average_html

        self._fill_plotly_chart(
            self._year_average_layout,
            points,
            build_html=build_year_average_html,
            chart_height=ANALYTICS_PLOTLY_BASE_HEIGHT,
            fallback=self._fill_year_average_fallback,
        )
