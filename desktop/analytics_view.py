"""Read-only desktop analytics view for watched scores."""

from __future__ import annotations

import os
import sys
import tempfile

from dataset.score_analytics import (
    build_score_analytics,
    format_rating_gap_line,
    format_suspicious_rating_line,
    summarize_dataset_completeness,
)
from desktop.theme import (
    COLOR_CARD,
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


# --- Базовая типографика вкладки «Аналитика» (QSS) ---

ANALYTICS_FONT_BASE = FONT_BASE
# Общий размер текста вкладки, если у виджета нет своего objectName.

ANALYTICS_FONT_PAGE_TITLE = FONT_TITLE
# Заголовок «Аналитика» вверху вкладки.

ANALYTICS_FONT_SUBTITLE = FONT_BASE
# Подзаголовок «Распределение моих оценок в watched-базе».

ANALYTICS_FONT_SECTION_TITLE = FONT_SECTION
# Заголовки секций: «Коротко», «Распределение оценок», «Одинаковые оценки».

ANALYTICS_FONT_SUMMARY_LABEL = FONT_SMALL
# Подписи KPI-карточек: «Всего», «Средняя», «Медиана», «Минимум», «Максимум».

ANALYTICS_FONT_SUMMARY_VALUE = FONT_KPI_VALUE
# Числа в KPI-карточках: 51, 6.8, 4.2 и т.д.

ANALYTICS_FONT_INSIGHT = FONT_BASE
# Строки текста в блоке «Коротко».

ANALYTICS_FONT_DENSE_COUNT = FONT_BASE
# Строка «N тайтлов» справа от оценки в «Одинаковые оценки».

ANALYTICS_FONT_DENSE_SCORE = FONT_DENSE_SCORE
# Число внутри зелёного badge с оценкой (6.5, 7.5, …).

ANALYTICS_FONT_SAME_SCORE_TITLES = FONT_SMALL
# Список названий тайтлов под строкой «N тайтлов».

ANALYTICS_FONT_FALLBACK = FONT_BASE
# Сообщение, если Plotly/WebEngine недоступен.


# --- Отступы и интервалы (layout) ---

ANALYTICS_ROOT_MARGIN = 14
# Поля вкладки от края прокручиваемой области.

ANALYTICS_ROOT_SPACING = 14
# Расстояние между заголовком, KPI-строкой и секциями.

ANALYTICS_SUMMARY_SPACING = 10
# Зазор между KPI-карточками в одной строке.

ANALYTICS_INSIGHT_LINE_SPACING = 8
# Расстояние между строками внутри блока «Коротко».

ANALYTICS_SECTION_PADDING = 16
# Внутренний отступ серых карточек секций от рамки.

ANALYTICS_SECTION_SPACING = 10
# Зазор между заголовком секции и её содержимым.

ANALYTICS_SUMMARY_CARD_PADDING = 12
# Внутренний отступ KPI-карточки от рамки.

ANALYTICS_SUMMARY_CARD_SPACING = 2
# Расстояние между подписью и числом внутри KPI-карточки.

ANALYTICS_DENSE_ROW_PADDING_X = 8
# Горизонтальный отступ строки в «Одинаковые оценки».

ANALYTICS_DENSE_ROW_PADDING_Y = 6
# Вертикальный отступ строки в «Одинаковые оценки».

ANALYTICS_DENSE_ROW_SPACING = 12
# Расстояние между badge с оценкой и текстовой колонкой.

ANALYTICS_DENSE_TEXT_SPACING = 2
# Расстояние между «N тайтлов» и списком названий.

SHOW_DENSE_SCORES_SECTION = False
# Секция «Одинаковые оценки» скрыта: insights в «Коротко» покрывают mode.

SUMMARY_CARD_HEIGHT = 88
# Высота KPI-карточки.

SUMMARY_ICON_BADGE_SIZE = 36
# Диаметр круглого badge с иконкой в KPI-карточке.

SECTION_HEADER_ICON_BADGE_SIZE = 28
# Диаметр badge иконки в заголовке секции.

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
    "Средняя моя оценка по годам": "↗",
    "Отличие моих оценок от IMDb": "±",
    "Я сильно выше IMDb": "↑",
    "Я сильно ниже IMDb": "↓",
    "Подозрительные оценки": "!",
}

DENSE_SCORE_BADGE_SIZE = 56
# Сторона квадратного badge с оценкой в «Одинаковые оценки».

BAR_TRACK_WIDTH = 330
# Ширина полосы fallback-графика (legacy helper, сейчас не используется в UI).

BAR_HEIGHT = 12
# Высота полосы fallback-графика (legacy helper).

BAR_TRACK_STYLE = build_bar_track_style()
BAR_FILL_STYLE = build_bar_fill_style()


def _build_analytics_style() -> str:
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


ANALYTICS_STYLE = _build_analytics_style()


def _format_metric(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.1f}"


def _entries_to_records(entries: list[tuple[str, dict, dict]]) -> dict:
    return {key: movie for key, movie, _card in entries}


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


class AnalyticsView:
    """Widget wrapper for read-only score analytics."""

    def __init__(self, entries: list[tuple[str, dict, dict]] | None = None) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

        self._plotly_html_paths: list[str] = []

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

        root_layout.addWidget(
            self._make_section(
                "Коротко",
                self._insights_layout,
                SECTION_ICONS["Коротко"],
                prefix_widgets=[self._completeness_headline, self._completeness_subline],
            )
        )

        self._distribution_layout = QVBoxLayout()
        root_layout.addWidget(
            self._make_section(
                "Распределение оценок",
                self._distribution_layout,
                SECTION_ICONS["Распределение оценок"],
                show_menu_stub=True,
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

    def update_entries(self, entries: list[tuple[str, dict, dict]]) -> None:
        analytics = build_score_analytics(_entries_to_records(entries), entries=entries)
        self._clear_plotly_html_files()
        self._fill_summary(analytics["summary"])
        self._fill_completeness(analytics["dataset_completeness"])
        self._fill_insights(analytics["insights"])
        self._fill_distribution(analytics["score_count_points"])
        self._fill_genre_count(analytics["genre_count_rows"])
        self._fill_year_average(analytics["year_average_points"])
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

    def _fill_summary(self, summary: dict) -> None:
        _clear_layout(self._summary_layout)
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
                self._make_summary_card(label, _format_metric(value), icon),
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
        _clear_layout(self._insights_layout)
        for text in insights:
            self._insights_layout.addWidget(self._make_insight_line(text))

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

    def _fill_distribution(self, points: list[dict]) -> None:
        from desktop.plotly_charts import SCORE_CHART_HEIGHT, build_score_count_html

        self._fill_plotly_chart(
            self._distribution_layout,
            points,
            build_html=build_score_count_html,
            chart_height=SCORE_CHART_HEIGHT,
            fallback=self._fill_distribution_fallback,
        )

    def _fill_genre_count(self, rows: list[dict]) -> None:
        from desktop.plotly_charts import GENRE_COUNT_CHART_HEIGHT, build_genre_count_html

        height = max(GENRE_COUNT_CHART_HEIGHT, 120 + len(rows) * 24)
        self._fill_plotly_chart(
            self._genre_count_layout,
            rows,
            build_html=build_genre_count_html,
            chart_height=height,
            fallback=self._fill_genre_count_fallback,
        )

    def _fill_year_average(self, points: list[dict]) -> None:
        from desktop.plotly_charts import YEAR_AVERAGE_CHART_HEIGHT, build_year_average_html

        self._fill_plotly_chart(
            self._year_average_layout,
            points,
            build_html=build_year_average_html,
            chart_height=YEAR_AVERAGE_CHART_HEIGHT,
            fallback=self._fill_year_average_fallback,
        )

    def _fill_imdb_delta(self, rows: list[dict], extra_count: int) -> None:
        from desktop.plotly_charts import IMDB_DELTA_CHART_HEIGHT, build_imdb_delta_html

        _clear_layout(self._imdb_delta_layout)
        if not rows:
            self._imdb_delta_layout.addWidget(
                self._make_list_placeholder("Нет тайтлов с вашей оценкой и IMDb для сравнения.")
            )
            return

        height = max(IMDB_DELTA_CHART_HEIGHT, 120 + len(rows) * 24)
        self._fill_plotly_chart(
            self._imdb_delta_layout,
            rows,
            build_html=build_imdb_delta_html,
            chart_height=height,
            fallback=lambda data, error: self._fill_imdb_delta_fallback(data, extra_count, error),
        )

    def _fill_plotly_chart(
        self,
        layout,
        data,
        *,
        build_html,
        chart_height: int,
        fallback,
    ) -> None:
        _clear_layout(layout)

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
            view.setFixedHeight(chart_height)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            view.setStyleSheet(f"background-color: {COLOR_CARD}; border: none;")
            html_path = self._write_plotly_html_file(html)
            view.setUrl(QUrl.fromLocalFile(html_path))
            layout.addWidget(view)
        except Exception as error:
            fallback(data, str(error))

    def _fill_rating_higher(self, rows: list[dict], extra_count: int) -> None:
        self._fill_text_list(
            self._rating_higher_layout,
            [format_rating_gap_line(row) for row in rows],
            empty_text="Нет тайтлов, где ваша оценка сильно выше IMDb.",
            extra_count=extra_count,
        )

    def _fill_rating_lower(self, rows: list[dict], extra_count: int) -> None:
        self._fill_text_list(
            self._rating_lower_layout,
            [format_rating_gap_line(row) for row in rows],
            empty_text="Нет тайтлов, где ваша оценка сильно ниже IMDb.",
            extra_count=extra_count,
        )

    def _fill_suspicious(self, rows: list[dict], extra_count: int) -> None:
        self._fill_text_list(
            self._suspicious_layout,
            [format_suspicious_rating_line(row) for row in rows],
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
        _clear_layout(layout)
        if not lines:
            layout.addWidget(self._make_list_placeholder(empty_text))
            return
        for line in lines:
            layout.addWidget(self._make_insight_line(line))
        if extra_count > 0:
            layout.addWidget(self._make_list_extra(f"ещё {extra_count}"))

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

    def _format_imdb_delta_fallback_line(self, row: dict) -> str:
        year = row.get("year")
        year_text = f" ({year})" if year not in (None, "") else ""
        delta = float(row["delta"])
        sign = "+" if delta > 0 else ""
        return (
            f"{row['title']}{year_text} · моя {float(row['user_score']):.1f} · "
            f"IMDb {float(row['imdb_score']):.1f} · {sign}{delta:.1f}"
        )

    def _fill_imdb_delta_fallback(
        self,
        rows: list[dict],
        extra_count: int,
        error: str | None = None,
    ) -> None:
        if error is not None:
            self._imdb_delta_layout.addWidget(
                self._make_fallback_message(
                    "Интерактивный график недоступен, показаны упрощённые строки.\n"
                    f"Python: {sys.executable}\n"
                    f"Ошибка: {error}"
                )
            )

        if not rows:
            self._imdb_delta_layout.addWidget(
                self._make_list_placeholder("Нет тайтлов с вашей оценкой и IMDb для сравнения.")
            )
            return

        for row in rows:
            self._imdb_delta_layout.addWidget(
                self._make_insight_line(self._format_imdb_delta_fallback_line(row))
            )
        if extra_count > 0:
            self._imdb_delta_layout.addWidget(self._make_list_extra(f"ещё {extra_count}"))

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

    def _fill_dense_scores(self, dense_scores: list[dict]) -> None:
        _clear_layout(self._dense_layout)
        if len(dense_scores) == 0:
            self._dense_layout.addWidget(self._make_dense_row({"score": None, "count": 0, "titles": [], "extra_count": 0}))
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

        score_text = "-" if dense_row.get("score") is None else _format_metric(dense_row["score"])
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
