"""Typography, spacing and icon constants for the analytics tab."""

from __future__ import annotations

from desktop.analytics.charts import CHART_BASE_HEIGHT
from desktop.theme import (
    FONT_BASE,
    FONT_DENSE_SCORE,
    FONT_KPI_VALUE,
    FONT_SECTION,
    FONT_SMALL,
    FONT_TITLE,
    build_analytics_style,
    build_bar_fill_style,
    build_bar_track_style,
)

ANALYTICS_FONT_BASE = FONT_BASE
ANALYTICS_FONT_PAGE_TITLE = FONT_TITLE
ANALYTICS_FONT_SUBTITLE = FONT_BASE
ANALYTICS_FONT_SECTION_TITLE = FONT_SECTION
ANALYTICS_FONT_SUMMARY_LABEL = FONT_SMALL
ANALYTICS_FONT_SUMMARY_VALUE = FONT_KPI_VALUE
ANALYTICS_FONT_INSIGHT = FONT_BASE
ANALYTICS_FONT_DENSE_COUNT = FONT_BASE
ANALYTICS_FONT_DENSE_SCORE = FONT_DENSE_SCORE
ANALYTICS_FONT_SAME_SCORE_TITLES = FONT_SMALL
ANALYTICS_FONT_FALLBACK = FONT_BASE

ANALYTICS_ROOT_MARGIN = 14
ANALYTICS_ROOT_SPACING = 14
ANALYTICS_SUMMARY_SPACING = 10
ANALYTICS_INSIGHT_LINE_SPACING = 4
ANALYTICS_COMPLETENESS_SPACING = 4
ANALYTICS_COMPLETENESS_BOTTOM_SPACING = 8
ANALYTICS_SECTION_PADDING = 16
ANALYTICS_SECTION_SPACING = 10
ANALYTICS_SUMMARY_CARD_PADDING = 12
ANALYTICS_SUMMARY_CARD_SPACING = 2
ANALYTICS_DENSE_ROW_PADDING_X = 8
ANALYTICS_DENSE_ROW_PADDING_Y = 6
ANALYTICS_DENSE_ROW_SPACING = 12
ANALYTICS_DENSE_TEXT_SPACING = 2

SHOW_DENSE_SCORES_SECTION = False

ANALYTICS_PLOTLY_BASE_HEIGHT = CHART_BASE_HEIGHT
ANALYTICS_PLOTLY_OBJECT_NAME = "analyticsPlotlyChart"

SUMMARY_CARD_HEIGHT = 88
SUMMARY_ICON_BADGE_SIZE = 36
SECTION_HEADER_ICON_BADGE_SIZE = 28

SUMMARY_CARD_ICONS = {
    "Всего": "▦",
    "Средняя": "↗",
    "Медиана": "◎",
    "Минимум": "↓",
    "Максимум": "↑",
}

SECTION_ICONS = {
    "Коротко": "☰",
    "Распределение оценок": "▤",
    "Количество тайтлов по жанрам": "▥",
    "Количество тайтлов по жанрам (pool)": "▦",
    "Средняя моя оценка по годам": "↗",
    "Отличие моих оценок от IMDb": "±",
    "Я сильно выше IMDb": "↑",
    "Я сильно ниже IMDb": "↓",
    "Подозрительные оценки": "!",
}

DENSE_SCORE_BADGE_SIZE = 56

BAR_TRACK_WIDTH = 330
BAR_HEIGHT = 12
BAR_TRACK_STYLE = build_bar_track_style()
BAR_FILL_STYLE = build_bar_fill_style()


def build_analytics_tab_style() -> str:
    return build_analytics_style(
        font_base=ANALYTICS_FONT_BASE,
        font_page_title=ANALYTICS_FONT_PAGE_TITLE,
        font_subtitle=ANALYTICS_FONT_SUBTITLE,
        font_section_title=ANALYTICS_FONT_SECTION_TITLE,
        font_summary_label=ANALYTICS_FONT_SUMMARY_LABEL,
        font_summary_value=ANALYTICS_FONT_SUMMARY_VALUE,
        font_insight=ANALYTICS_FONT_INSIGHT,
        font_dense_count=ANALYTICS_FONT_DENSE_COUNT,
        font_dense_score=ANALYTICS_FONT_DENSE_SCORE,
        font_same_score_titles=ANALYTICS_FONT_SAME_SCORE_TITLES,
        font_fallback=ANALYTICS_FONT_FALLBACK,
    )


ANALYTICS_STYLE = build_analytics_tab_style()
