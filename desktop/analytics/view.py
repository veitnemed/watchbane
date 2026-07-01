"""Read-only desktop analytics view for watched scores."""

from __future__ import annotations

from collections.abc import Callable

from dataset.score_analytics import build_score_analytics

from desktop.analytics.constants import (
    ANALYTICS_COMPLETENESS_BOTTOM_SPACING,
    ANALYTICS_COMPLETENESS_SPACING,
    ANALYTICS_INSIGHT_LINE_SPACING,
    ANALYTICS_ROOT_MARGIN,
    ANALYTICS_ROOT_SPACING,
    ANALYTICS_STYLE,
    ANALYTICS_SUMMARY_SPACING,
    SECTION_ICONS,
    SHOW_DENSE_SCORES_SECTION,
)
from desktop.analytics.sections.charts_host import AnalyticsChartsMixin
from desktop.analytics.sections.common import AnalyticsSectionUIMixin, entries_to_records
from desktop.analytics.sections.fallback_bars import AnalyticsFallbackMixin
from desktop.analytics.sections.lists import AnalyticsListsMixin
from desktop.analytics.sections.summary import AnalyticsSummaryMixin

# Re-export for tests and theme contract checks.
from desktop.analytics.constants import ANALYTICS_PLOTLY_OBJECT_NAME  # noqa: F401


class AnalyticsView(
    AnalyticsSectionUIMixin,
    AnalyticsSummaryMixin,
    AnalyticsChartsMixin,
    AnalyticsFallbackMixin,
    AnalyticsListsMixin,
):
    """Widget wrapper for read-only score analytics."""

    def __init__(
        self,
        entries: list[tuple[str, dict, dict]] | None = None,
        *,
        entries_provider: Callable[[], list[tuple[str, dict, dict]]] | None = None,
    ) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

        self._plotly_html_paths: list[str] = []
        self._entries_provider = entries_provider

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(ANALYTICS_STYLE)

        self._root = QWidget()
        self._root.setObjectName("analyticsRoot")
        self._root.setStyleSheet(ANALYTICS_STYLE)
        self._scroll.setWidget(self._root)

        root_layout = QVBoxLayout(self._root)
        root_layout.setContentsMargins(
            ANALYTICS_ROOT_MARGIN,
            ANALYTICS_ROOT_MARGIN,
            ANALYTICS_ROOT_MARGIN,
            ANALYTICS_ROOT_MARGIN,
        )
        root_layout.setSpacing(ANALYTICS_ROOT_SPACING)

        title = QLabel("Аналитика")
        title.setObjectName("analyticsTitle")
        root_layout.addWidget(title)

        subtitle = QLabel("Распределение моих оценок в watched-базе")
        subtitle.setObjectName("analyticsSubtitle")
        root_layout.addWidget(subtitle)

        self._summary_layout = QHBoxLayout()
        self._summary_layout.setSpacing(ANALYTICS_SUMMARY_SPACING)
        self._summary_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        root_layout.addLayout(self._summary_layout)

        self._insights_layout = QVBoxLayout()
        self._insights_layout.setSpacing(ANALYTICS_INSIGHT_LINE_SPACING)

        self._completeness_headline = QLabel("Полнота dataset: 0%")
        self._completeness_headline.setObjectName("completenessHeadline")
        self._completeness_subline = QLabel("")
        self._completeness_subline.setObjectName("completenessSubline")
        self._completeness_subline.setWordWrap(True)

        completeness_layout = QVBoxLayout()
        completeness_layout.setContentsMargins(0, 0, 0, 0)
        completeness_layout.setSpacing(ANALYTICS_COMPLETENESS_SPACING)
        completeness_layout.addWidget(self._completeness_headline)
        completeness_layout.addWidget(self._completeness_subline)

        insights_wrapper = QVBoxLayout()
        insights_wrapper.setContentsMargins(0, ANALYTICS_COMPLETENESS_BOTTOM_SPACING, 0, 0)
        insights_wrapper.setSpacing(0)
        insights_wrapper.addLayout(self._insights_layout)

        short_section_content = QVBoxLayout()
        short_section_content.setContentsMargins(0, 0, 0, 0)
        short_section_content.setSpacing(0)
        short_section_content.addLayout(completeness_layout)
        short_section_content.addLayout(insights_wrapper)

        root_layout.addWidget(
            self._make_section(
                "Коротко",
                short_section_content,
                SECTION_ICONS["Коротко"],
            )
        )

        self._distribution_layout = QVBoxLayout()
        root_layout.addWidget(
            self._make_section(
                "Распределение оценок",
                self._distribution_layout,
                SECTION_ICONS["Распределение оценок"],
            )
        )

        self._genre_count_layout = QVBoxLayout()
        root_layout.addWidget(
            self._make_section(
                "Количество тайтлов по жанрам",
                self._genre_count_layout,
                SECTION_ICONS["Количество тайтлов по жанрам"],
            )
        )

        self._year_average_layout = QVBoxLayout()
        root_layout.addWidget(
            self._make_section(
                "Средняя моя оценка по годам",
                self._year_average_layout,
                SECTION_ICONS["Средняя моя оценка по годам"],
            )
        )

        self._imdb_delta_layout = QVBoxLayout()
        self._imdb_delta_rows: list[dict] = []
        self._imdb_delta_extra_count = 0
        self._imdb_delta_expanded = False
        root_layout.addWidget(
            self._make_section(
                "Отличие моих оценок от IMDb",
                self._imdb_delta_layout,
                SECTION_ICONS["Отличие моих оценок от IMDb"],
            )
        )

        self._rating_higher_layout = QVBoxLayout()
        root_layout.addWidget(
            self._make_section(
                "Я сильно выше IMDb",
                self._rating_higher_layout,
                SECTION_ICONS["Я сильно выше IMDb"],
            )
        )

        self._rating_lower_layout = QVBoxLayout()
        root_layout.addWidget(
            self._make_section(
                "Я сильно ниже IMDb",
                self._rating_lower_layout,
                SECTION_ICONS["Я сильно ниже IMDb"],
            )
        )

        self._suspicious_layout = QVBoxLayout()
        root_layout.addWidget(
            self._make_section(
                "Подозрительные оценки",
                self._suspicious_layout,
                SECTION_ICONS["Подозрительные оценки"],
            )
        )

        self._dense_layout = QVBoxLayout()
        if SHOW_DENSE_SCORES_SECTION:
            root_layout.addWidget(
                self._make_section("Одинаковые оценки", self._dense_layout, "◎")
            )

        root_layout.addStretch()
        self.update_entries(entries or [])

    @property
    def widget(self):
        return self._scroll

    def on_tab_activated(self) -> None:
        if self._entries_provider is not None:
            self.update_entries(self._entries_provider())

    def update_entries(self, entries: list[tuple[str, dict, dict]]) -> None:
        analytics = build_score_analytics(entries_to_records(entries), entries=entries)
        self._clear_plotly_html_files()
        self._fill_summary(analytics["summary"])
        self._fill_completeness(analytics["dataset_completeness"])
        self._fill_insights(analytics["insights"])
        self._fill_distribution(analytics["score_count_points"])
        self._fill_genre_count(analytics["genre_count_rows"])
        self._fill_year_average(analytics["year_average_points"])
        self._imdb_delta_expanded = False
        self._fill_imdb_delta(
            analytics["imdb_delta_rows"],
            analytics["imdb_delta_extra_count"],
        )
        self._fill_rating_higher(
            analytics["rating_higher_than_public"],
            analytics["rating_higher_extra_count"],
        )
        self._fill_rating_lower(
            analytics["rating_lower_than_public"],
            analytics["rating_lower_extra_count"],
        )
        self._fill_suspicious(
            analytics["suspicious_ratings"],
            analytics["suspicious_extra_count"],
        )
        if SHOW_DENSE_SCORES_SECTION:
            self._fill_dense_scores(analytics["dense_scores"])
