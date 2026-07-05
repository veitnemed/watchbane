"""Read-only desktop analytics view for watched scores."""

from __future__ import annotations

from collections.abc import Callable

from candidates.service import get_pool_genre_count_rows, get_pool_view

from desktop.analytics.chart_constructor import (
    CHART_FUNCTION,
    SOURCE_CANDIDATE_POOL,
    SOURCE_WATCHED,
    X_USER_SCORE,
    Y_COUNT,
    build_chart_constructor_data,
)
from desktop.analytics.constants import (
    ANALYTICS_ROOT_MARGIN,
    ANALYTICS_ROOT_SPACING,
    ANALYTICS_STYLE,
    SECTION_ICONS,
)
from desktop.analytics.charts import CHART_BASE_HEIGHT
from desktop.theme.scaling import layout_px
from desktop.analytics.sections.charts_host import AnalyticsChartsMixin
from desktop.analytics.sections.common import AnalyticsSectionUIMixin, clear_layout
from desktop.analytics.sections.fallback_bars import AnalyticsFallbackMixin
from dataset.analytics.reports import build_genre_count_rows

# Re-export for tests and theme contract checks.
from desktop.analytics.constants import ANALYTICS_PLOTLY_OBJECT_NAME  # noqa: F401


class AnalyticsView(
    AnalyticsSectionUIMixin,
    AnalyticsChartsMixin,
    AnalyticsFallbackMixin,
):
    """Widget wrapper for read-only score analytics."""

    def __init__(
        self,
        entries: list[tuple[str, dict, dict]] | None = None,
        *,
        entries_provider: Callable[[], list[tuple[str, dict, dict]]] | None = None,
    ) -> None:
        from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

        self._plotly_html_paths: list[str] = []
        self._entries_provider = entries_provider
        self._entries: list[tuple[str, dict, dict]] = []

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

        title = QLabel("Информация")
        title.setObjectName("analyticsTitle")
        root_layout.addWidget(title)

        subtitle = QLabel("Готовые жанровые отчёты и конструктор графика")
        subtitle.setObjectName("analyticsSubtitle")
        root_layout.addWidget(subtitle)

        self._genre_count_layout = QVBoxLayout()
        root_layout.addWidget(
            self._make_section(
                "Количество тайтлов по жанрам",
                self._genre_count_layout,
                SECTION_ICONS["Количество тайтлов по жанрам"],
            )
        )

        self._pool_genre_count_layout = QVBoxLayout()
        root_layout.addWidget(
            self._make_section(
                "Количество тайтлов по жанрам (pool)",
                self._pool_genre_count_layout,
                SECTION_ICONS["Количество тайтлов по жанрам (pool)"],
            )
        )

        self._chart_constructor_layout = QVBoxLayout()
        root_layout.addWidget(
            self._make_section(
                "Конструктор графика",
                self._chart_constructor_layout,
                SECTION_ICONS["Конструктор графика"],
            )
        )
        self._build_chart_constructor_controls()

        root_layout.addStretch()
        self.update_entries(entries or [])

    @property
    def widget(self):
        return self._scroll

    def on_tab_activated(self) -> None:
        if self._entries_provider is not None:
            self.update_entries(self._entries_provider())

    def update_entries(self, entries: list[tuple[str, dict, dict]]) -> None:
        self._entries = list(entries)
        self._clear_plotly_html_files()
        self._fill_genre_count(build_genre_count_rows(entries))
        self._fill_pool_genre_count(get_pool_genre_count_rows())
        self._render_chart_constructor()

    def _build_chart_constructor_controls(self) -> None:
        from PyQt6.QtWidgets import QComboBox, QFrame, QGridLayout, QPushButton, QVBoxLayout

        controls_panel = QFrame()
        controls_panel.setObjectName("chartConstructorControls")
        controls_layout = QGridLayout(controls_panel)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setHorizontalSpacing(12)
        controls_layout.setVerticalSpacing(10)
        controls_layout.setColumnStretch(0, 2)
        controls_layout.setColumnStretch(1, 1)
        controls_layout.setColumnStretch(2, 2)
        controls_layout.setColumnStretch(3, 2)
        controls_layout.setColumnStretch(4, 1)

        self._chart_source_combo = QComboBox()
        self._chart_source_combo.setObjectName("chartConstructorCombo")
        self._chart_source_combo.addItem("Просмотренные тайтлы", SOURCE_WATCHED)
        self._chart_source_combo.addItem("Candidate pool", SOURCE_CANDIDATE_POOL)

        self._chart_type_combo = QComboBox()
        self._chart_type_combo.setObjectName("chartConstructorCombo")
        self._chart_type_combo.addItem("Столбчатый", "bar")
        self._chart_type_combo.addItem("Функция", CHART_FUNCTION)

        self._chart_x_combo = QComboBox()
        self._chart_x_combo.setObjectName("chartConstructorCombo")
        self._chart_x_combo.addItem("Оценка пользователя", X_USER_SCORE)
        self._chart_x_combo.addItem("Год", "year")
        self._chart_x_combo.addItem("Жанр", "genre")
        self._chart_x_combo.addItem("Страна", "country")
        self._chart_x_combo.addItem("TMDb рейтинг", "tmdb_score")
        self._chart_x_combo.addItem("TMDb голоса", "tmdb_votes")
        self._chart_x_combo.addItem("TMDb popularity", "tmdb_popularity")

        self._chart_y_combo = QComboBox()
        self._chart_y_combo.setObjectName("chartConstructorCombo")
        self._chart_y_combo.addItem("Количество тайтлов", Y_COUNT)
        self._chart_y_combo.addItem("Средняя пользовательская оценка", "avg_user_score")
        self._chart_y_combo.addItem("Средний TMDb рейтинг", "avg_tmdb_score")
        self._chart_y_combo.addItem("Средний итоговый score", "avg_final_score")

        self._chart_step_combo = QComboBox()
        self._chart_step_combo.setObjectName("chartConstructorCombo")
        self._chart_step_combo.addItem("1.0", 1.0)
        self._chart_step_combo.addItem("0.5", 0.5)

        self._add_labeled_combo(controls_layout, 0, 0, "Источник данных", self._chart_source_combo)
        self._add_labeled_combo(controls_layout, 0, 1, "Тип графика", self._chart_type_combo)
        self._add_labeled_combo(controls_layout, 0, 2, "Ось X", self._chart_x_combo)
        self._add_labeled_combo(controls_layout, 0, 3, "Ось Y", self._chart_y_combo)
        self._add_labeled_combo(controls_layout, 0, 4, "Шаг", self._chart_step_combo)

        self._build_chart_button = QPushButton("Построить график")
        self._build_chart_button.setObjectName("chartConstructorBuildButton")
        self._build_chart_button.clicked.connect(self._render_chart_constructor)
        controls_layout.addWidget(self._build_chart_button, 1, 0, 1, 5)

        self._chart_constructor_layout.addWidget(controls_panel)
        self._chart_builder_result_layout = QVBoxLayout()
        self._chart_builder_result_layout.setContentsMargins(0, layout_px(6), 0, 0)
        self._chart_constructor_layout.addLayout(self._chart_builder_result_layout)

    def _add_labeled_combo(self, layout, row: int, column: int, label_text: str, combo) -> None:
        from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

        box = QWidget()
        box.setObjectName("chartConstructorField")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(layout_px(4))
        label = QLabel(label_text)
        label.setObjectName("chartConstructorLabel")
        box_layout.addWidget(label)
        box_layout.addWidget(combo)
        layout.addWidget(box, row, column)

    def _combo_value(self, combo):
        value = combo.currentData()
        return value if value is not None else combo.currentText()

    def _render_chart_constructor(self) -> None:
        from desktop.analytics.charts import build_constructor_chart_html

        result = build_chart_constructor_data(
            source=self._combo_value(self._chart_source_combo),
            x_axis=self._combo_value(self._chart_x_combo),
            y_axis=self._combo_value(self._chart_y_combo),
            chart_type=self._combo_value(self._chart_type_combo),
            step=self._combo_value(self._chart_step_combo),
            watched_entries=self._entries,
            candidate_entries=get_pool_view(),
        )
        clear_layout(self._chart_builder_result_layout)

        if result["ok"] is False:
            self._chart_builder_result_layout.addWidget(
                self._make_list_placeholder(result["message"])
            )
            return

        self._fill_plotly_chart(
            self._chart_builder_result_layout,
            result,
            build_html=build_constructor_chart_html,
            chart_height=CHART_BASE_HEIGHT,
            fallback=self._fill_chart_constructor_fallback,
        )

    def _fill_chart_constructor_fallback(self, payload: dict, error: str | None = None) -> None:
        if error is not None:
            self._chart_builder_result_layout.addWidget(
                self._make_fallback_message(
                    "Интерактивный график недоступен, показаны упрощённые полосы.\n"
                    f"Ошибка: {error}"
                )
            )
        rows = payload.get("rows") or []
        max_count = max((int(row.get("count") or 0) for row in rows), default=0)
        for row in rows:
            self._chart_builder_result_layout.addWidget(self._make_bar_row(row, max_count))
