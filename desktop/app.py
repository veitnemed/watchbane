"""PyQt6 desktop viewer for watched movies and series."""

from __future__ import annotations

import sys

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.analytics_view import AnalyticsView
from desktop.model_view import ModelView
from desktop.delete_dialog import WatchedDeleteDialog
from desktop.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_SOFT,
    COLOR_BORDER,
    COLOR_CARD_ALT,
    COLOR_TEXT,
    FONT_FAMILY,
    build_app_style,
    build_score_edit_dialog_style,
)
from desktop.watched_view import (
    GENRE_FILTER_ALL,
    SORT_OPTIONS,
    USER_SCORE_MAX,
    USER_SCORE_MIN,
    USER_SCORE_STEP,
    YEAR_FILTER_DEFAULT_FROM,
    YEAR_FILTER_DEFAULT_TO,
    YEAR_FILTER_MAX,
    YEAR_FILTER_MIN,
    WatchedDetailCard,
    WatchedEntry,
    WatchedListItemDelegate,
    apply_view,
    format_list_label,
    format_save_user_score_status,
    format_user_score_display,
    format_watched_filters_label,
    format_watched_list_counter,
    format_watched_list_status,
    genre_filter_is_active,
    get_available_genres,
    get_user_score_spin_value,
    load_watched_entries,
    save_watched_user_score,
    score_filter_is_active,
    validate_score_edit_entry,
    watched_filters_are_active,
    year_filter_is_active,
)
from desktop.watched_delete import (
    execute_watched_delete,
    format_delete_status_message,
    load_delete_preview,
)

DARK_STYLE = build_app_style()
SCORE_EDIT_DIALOG_STYLE = build_score_edit_dialog_style()


class RangeSlider(QWidget):
    """Compact two-handle horizontal range slider."""

    rangeChanged = pyqtSignal(int, int)

    def __init__(self, minimum: int, maximum: int, lower: int, upper: int, parent=None) -> None:
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._lower = lower
        self._upper = upper
        self._active_handle = "lower"
        self._dragging = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(30)

    def sizeHint(self) -> QSize:
        return QSize(180, 30)

    def values(self) -> tuple[int, int]:
        return (self._lower, self._upper)

    def setValues(self, lower: int, upper: int) -> None:
        lower = self._clamp(lower)
        upper = self._clamp(upper)
        if lower > upper:
            lower, upper = upper, lower
        if (lower, upper) == (self._lower, self._upper):
            return
        self._lower = lower
        self._upper = upper
        self.update()
        self.rangeChanged.emit(self._lower, self._upper)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        handle_radius = 7
        track_height = 4
        left = handle_radius + 2
        right = self.width() - handle_radius - 2
        center_y = self.height() / 2

        track = QRectF(left, center_y - track_height / 2, right - left, track_height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLOR_CARD_ALT))
        painter.drawRoundedRect(track, track_height / 2, track_height / 2)

        lower_x = self._x_from_value(self._lower)
        upper_x = self._x_from_value(self._upper)
        active = QRectF(lower_x, center_y - track_height / 2, upper_x - lower_x, track_height)
        painter.setBrush(QColor(COLOR_ACCENT_SOFT))
        painter.drawRoundedRect(active, track_height / 2, track_height / 2)

        handle_pen = QPen(QColor(COLOR_BORDER), 1)
        for x in (lower_x, upper_x):
            painter.setPen(handle_pen)
            painter.setBrush(QColor(COLOR_ACCENT))
            painter.drawEllipse(QRectF(x - handle_radius, center_y - handle_radius, handle_radius * 2, handle_radius * 2))
            painter.setPen(QPen(QColor(COLOR_TEXT), 1))
            painter.drawEllipse(QRectF(x - 2, center_y - 2, 4, 4))

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        lower_distance = abs(event.position().x() - self._x_from_value(self._lower))
        upper_distance = abs(event.position().x() - self._x_from_value(self._upper))
        self._active_handle = "lower" if lower_distance <= upper_distance else "upper"
        self._dragging = True
        self._move_active_handle(event.position().x())

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._move_active_handle(event.position().x())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def keyPressEvent(self, event) -> None:
        if event.key() not in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            super().keyPressEvent(event)
            return
        delta = -1 if event.key() == Qt.Key.Key_Left else 1
        if self._active_handle == "lower":
            self.setValues(min(self._lower + delta, self._upper), self._upper)
        else:
            self.setValues(self._lower, max(self._upper + delta, self._lower))

    def _move_active_handle(self, x: float) -> None:
        value = self._value_from_x(x)
        if self._active_handle == "lower":
            self.setValues(min(value, self._upper), self._upper)
        else:
            self.setValues(self._lower, max(value, self._lower))

    def _clamp(self, value: int) -> int:
        return max(self._minimum, min(self._maximum, int(value)))

    def _x_from_value(self, value: int) -> float:
        handle_radius = 7
        left = handle_radius + 2
        right = self.width() - handle_radius - 2
        if self._maximum == self._minimum:
            return left
        ratio = (value - self._minimum) / (self._maximum - self._minimum)
        return left + ratio * (right - left)

    def _value_from_x(self, x: float) -> int:
        handle_radius = 7
        left = handle_radius + 2
        right = self.width() - handle_radius - 2
        if right <= left:
            return self._minimum
        ratio = max(0.0, min(1.0, (x - left) / (right - left)))
        return round(self._minimum + ratio * (self._maximum - self._minimum))


class ScoreEditDialog(QDialog):
    """Compact dark dialog for editing a watched title score."""

    def __init__(self, entry: WatchedEntry, parent=None) -> None:
        super().__init__(parent)
        dataset_key, _movie, card = entry
        title = card.get("title") or dataset_key
        year = card.get("year")
        title_text = f"{title} ({year})" if year not in (None, "") else str(title)

        self.setObjectName("scoreEditDialog")
        self.setWindowTitle("Изменить оценку")
        self.setModal(True)
        self.setFixedWidth(390)
        self.setStyleSheet(SCORE_EDIT_DIALOG_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(0)

        card_frame = QFrame()
        card_frame.setObjectName("scoreEditCard")
        root_layout.addWidget(card_frame)

        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        header = QLabel("Изменить оценку")
        header.setObjectName("scoreEditTitle")
        card_layout.addWidget(header)

        title_label = QLabel(title_text)
        title_label.setObjectName("scoreEditMovieTitle")
        title_label.setWordWrap(True)
        card_layout.addWidget(title_label)

        current_label = QLabel(f"Текущая оценка: {format_user_score_display(card.get('user_score'))}")
        current_label.setObjectName("scoreEditCurrent")
        card_layout.addWidget(current_label)

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setSpacing(8)
        field_label = QLabel("Новая оценка")
        field_label.setObjectName("scoreEditFieldLabel")
        self._score_input = QDoubleSpinBox()
        self._score_input.setObjectName("scoreEditSpin")
        self._score_input.setRange(USER_SCORE_MIN, USER_SCORE_MAX)
        self._score_input.setSingleStep(USER_SCORE_STEP)
        self._score_input.setDecimals(1)
        self._score_input.setValue(get_user_score_spin_value(card))
        self._score_input.selectAll()
        form.addRow(field_label, self._score_input)
        card_layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setObjectName("scoreEditSaveButton")
            save_button.setText("Сохранить")
            save_button.setDefault(True)
            save_button.setAutoDefault(True)
        if cancel_button is not None:
            cancel_button.setText("Отмена")
            cancel_button.setAutoDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        card_layout.addWidget(buttons)

        self._score_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def score_value(self) -> float:
        return self._score_input.value()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            return
        super().keyPressEvent(event)


class WatchedMoviesWindow(QMainWindow):
    """Main window for browsing watched titles."""

    def __init__(self) -> None:
        super().__init__()
        self._entries: list[WatchedEntry] = load_watched_entries()
        self._visible_entries: list[WatchedEntry] = list(self._entries)
        self._sort_key = SORT_OPTIONS[0][0]

        self.setWindowTitle("Terminal Movies Learn Desktop")
        self.resize(1180, 720)
        self.setStyleSheet(DARK_STYLE)
        self.statusBar().showMessage("")

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        watched_tab = QWidget()
        layout = QHBoxLayout(watched_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 840])

        tabs.addTab(watched_tab, "Watched")
        self._analytics_view = AnalyticsView(self._entries)
        tabs.addTab(self._analytics_view.widget, "Аналитика")
        self._model_view = ModelView()
        tabs.addTab(self._model_view.widget, "Модель")

        self._refresh_list()
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("watchedSidebar")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(400)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self._add_title_button = QPushButton("+ Добавить тайтл")
        self._add_title_button.setObjectName("watchedAddTitle")
        self._add_title_button.clicked.connect(self._open_add_title_dialog)
        layout.addWidget(self._add_title_button)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("watchedSearch")
        self._search_input.setPlaceholderText("Поиск по названию")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._on_filters_changed)
        layout.addWidget(self._search_input)

        sort_row = QWidget()
        sort_row.setObjectName("watchedSortRow")
        sort_layout = QHBoxLayout(sort_row)
        sort_layout.setContentsMargins(0, 0, 0, 0)
        sort_layout.setSpacing(10)

        sort_label = QLabel("Сортировка")
        sort_label.setObjectName("watchedSortLabel")

        self._sort_combo = QComboBox()
        self._sort_combo.setObjectName("watchedSort")
        for sort_key, label in SORT_OPTIONS:
            self._sort_combo.addItem(label, sort_key)
        self._sort_combo.currentIndexChanged.connect(self._on_filters_changed)

        sort_layout.addWidget(sort_label)
        sort_layout.addWidget(self._sort_combo, stretch=1)
        layout.addWidget(sort_row)

        self._filters_expanded = False
        self._filter_toggle = QPushButton("▸ Фильтры")
        self._filter_toggle.setObjectName("watchedFilterToggle")
        self._filter_toggle.clicked.connect(self._toggle_filters_panel)
        layout.addWidget(self._filter_toggle)

        self._filters_panel = self._build_filters_panel()
        self._filters_panel.setVisible(False)
        layout.addWidget(self._filters_panel)

        self._list_counter_label = QLabel("")
        self._list_counter_label.setObjectName("watchedListCounter")
        layout.addWidget(self._list_counter_label)

        self._list_widget = QListWidget()
        self._list_widget.setObjectName("watchedList")
        self._list_widget.setSpacing(2)
        self._list_widget.setUniformItemSizes(True)
        self._list_widget.setItemDelegate(WatchedListItemDelegate(self._list_widget))
        self._list_widget.currentRowChanged.connect(self._on_selection_changed)
        self._list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_widget.customContextMenuRequested.connect(self._open_list_context_menu)
        layout.addWidget(self._list_widget, stretch=1)

        return panel

    def _build_filters_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("watchedFiltersPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        layout.addWidget(self._build_score_filter_panel())
        layout.addWidget(self._build_year_filter_panel())
        layout.addWidget(self._build_genre_filter_panel())

        reset_all_button = QPushButton("Сбросить фильтры")
        reset_all_button.setObjectName("watchedFilterResetAll")
        reset_all_button.clicked.connect(self._reset_all_filters)
        layout.addWidget(reset_all_button)
        return frame

    def _toggle_filters_panel(self) -> None:
        self._filters_expanded = not self._filters_expanded
        self._filters_panel.setVisible(self._filters_expanded)
        self._update_filter_toggle_label()

    def _update_filter_toggle_label(self) -> None:
        score_active = self._score_filter_active()
        year_active = self._year_filter_active()
        genre_active = self._genre_filter_active()
        filters_active = watched_filters_are_active(score_active, year_active, genre_active)
        self._filter_toggle.setText(
            format_watched_filters_label(
                score_active,
                year_active,
                genre_active,
                self._filters_expanded,
            )
        )
        self._filter_toggle.setProperty("watchedFiltersActive", "true" if filters_active else "false")
        self._filter_toggle.style().unpolish(self._filter_toggle)
        self._filter_toggle.style().polish(self._filter_toggle)

    def _reset_all_filters(self) -> None:
        self._score_slider.blockSignals(True)
        self._score_slider.setValues(
            self._score_to_slider_value(USER_SCORE_MIN),
            self._score_to_slider_value(USER_SCORE_MAX),
        )
        self._score_slider.blockSignals(False)

        self._year_slider.blockSignals(True)
        self._year_slider.setValues(YEAR_FILTER_DEFAULT_FROM, YEAR_FILTER_DEFAULT_TO)
        self._year_slider.blockSignals(False)

        self._genre_combo.blockSignals(True)
        self._genre_combo.setCurrentIndex(0)
        self._genre_combo.blockSignals(False)

        self._update_score_range_label()
        self._update_year_range_label()
        self._on_filters_changed()

    def _build_score_filter_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("watchedScoreFilter")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Оценка")
        title.setObjectName("watchedScoreFilterTitle")
        header_row.addWidget(title)
        header_row.addStretch()

        self._score_range_label = QLabel()
        self._score_range_label.setObjectName("watchedFilterValue")
        header_row.addWidget(self._score_range_label)
        layout.addLayout(header_row)

        self._score_slider = RangeSlider(
            self._score_to_slider_value(USER_SCORE_MIN),
            self._score_to_slider_value(USER_SCORE_MAX),
            self._score_to_slider_value(USER_SCORE_MIN),
            self._score_to_slider_value(USER_SCORE_MAX),
        )
        self._score_slider.setObjectName("watchedScoreRange")
        self._score_slider.rangeChanged.connect(self._on_score_range_changed)
        layout.addWidget(self._score_slider)
        self._update_score_range_label()
        return frame

    def _score_to_slider_value(self, score: float) -> int:
        return int(round(float(score) / USER_SCORE_STEP))

    def _score_from_slider_value(self, value: int) -> float:
        return round(value * USER_SCORE_STEP, 1)

    def _score_filter_range(self) -> tuple[float, float]:
        lower, upper = self._score_slider.values()
        return (self._score_from_slider_value(lower), self._score_from_slider_value(upper))

    def _score_filter_active(self) -> bool:
        min_score, max_score = self._score_filter_range()
        return score_filter_is_active(min_score, max_score)

    def _update_score_range_label(self) -> None:
        min_score, max_score = self._score_filter_range()
        self._score_range_label.setText(f"{min_score:.1f}-{max_score:.1f}")

    def _on_score_range_changed(self, _lower: int, _upper: int) -> None:
        self._update_score_range_label()
        self._on_filters_changed()

    def _reset_score_filter(self) -> None:
        self._score_slider.blockSignals(True)
        self._score_slider.setValues(
            self._score_to_slider_value(USER_SCORE_MIN),
            self._score_to_slider_value(USER_SCORE_MAX),
        )
        self._score_slider.blockSignals(False)
        self._update_score_range_label()
        self._on_filters_changed()

    def _build_year_filter_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("watchedYearFilter")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Год")
        title.setObjectName("watchedYearFilterTitle")
        header_row.addWidget(title)
        header_row.addStretch()

        self._year_range_label = QLabel()
        self._year_range_label.setObjectName("watchedFilterValue")
        header_row.addWidget(self._year_range_label)
        layout.addLayout(header_row)

        self._year_slider = RangeSlider(
            YEAR_FILTER_MIN,
            YEAR_FILTER_MAX,
            YEAR_FILTER_DEFAULT_FROM,
            YEAR_FILTER_DEFAULT_TO,
        )
        self._year_slider.setObjectName("watchedYearRange")
        self._year_slider.rangeChanged.connect(self._on_year_range_changed)
        layout.addWidget(self._year_slider)
        self._update_year_range_label()
        return frame

    def _year_filter_range(self) -> tuple[int, int]:
        return self._year_slider.values()

    def _year_filter_active(self) -> bool:
        year_from, year_to = self._year_filter_range()
        return year_filter_is_active(year_from, year_to)

    def _update_year_range_label(self) -> None:
        year_from, year_to = self._year_filter_range()
        self._year_range_label.setText(f"{year_from}-{year_to}")

    def _on_year_range_changed(self, _lower: int, _upper: int) -> None:
        self._update_year_range_label()
        self._on_filters_changed()

    def _reset_year_filter(self) -> None:
        self._year_slider.blockSignals(True)
        self._year_slider.setValues(YEAR_FILTER_DEFAULT_FROM, YEAR_FILTER_DEFAULT_TO)
        self._year_slider.blockSignals(False)
        self._update_year_range_label()
        self._on_filters_changed()

    def _build_genre_filter_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("watchedGenreFilter")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Жанр")
        title.setObjectName("watchedGenreFilterTitle")
        layout.addWidget(title)

        self._genre_combo = QComboBox()
        self._genre_combo.setObjectName("watchedGenre")
        self._genre_combo.addItem(GENRE_FILTER_ALL, None)
        for genre in get_available_genres(self._entries):
            self._genre_combo.addItem(genre, genre)
        self._genre_combo.currentIndexChanged.connect(self._on_filters_changed)
        layout.addWidget(self._genre_combo)
        return frame

    def _open_add_title_dialog(self) -> None:
        from desktop.add_title_dialog import run_add_title_flow

        result = run_add_title_flow(self)
        if result is None or result.ok is False:
            return

        added_key = result.title
        self._entries = load_watched_entries()
        self._analytics_view.update_entries(self._entries)
        self._model_view.refresh()
        self._refresh_list()

        for index, (key, _, _) in enumerate(self._visible_entries):
            if key == added_key:
                self._list_widget.blockSignals(True)
                self._list_widget.setCurrentRow(index)
                self._list_widget.blockSignals(False)
                self._detail_card.show_entry(self._visible_entries[index])
                break

        self.statusBar().showMessage(result.message or "Новая запись добавлена!", 5000)

    def _selected_genre_filter(self) -> str | None:
        genre = self._genre_combo.currentData()
        return genre if isinstance(genre, str) else None

    def _genre_filter_active(self) -> bool:
        return genre_filter_is_active(self._selected_genre_filter())

    def _build_right_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._detail_card = WatchedDetailCard()
        scroll.setWidget(self._detail_card.widget)
        return scroll

    def _current_entry_key(self) -> str | None:
        row = self._list_widget.currentRow()
        if row < 0 or row >= len(self._visible_entries):
            return None
        return self._visible_entries[row][0]

    def _refresh_after_user_score_save(self, current_key: str, result) -> None:
        self._entries = load_watched_entries()
        self._analytics_view.update_entries(self._entries)
        self._model_view.refresh()
        self._refresh_list()

        for index, (key, _, _) in enumerate(self._visible_entries):
            if key == current_key:
                self._list_widget.blockSignals(True)
                self._list_widget.setCurrentRow(index)
                self._list_widget.blockSignals(False)
                self._detail_card.show_entry(self._visible_entries[index])
                break

        self.statusBar().showMessage(format_save_user_score_status(result), 4000)

    def _entry_from_item(self, item) -> WatchedEntry | None:
        if item is None:
            return None
        entry = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(entry, tuple) and len(entry) == 3:
            return entry
        return None

    def _open_list_context_menu(self, position) -> None:
        item = self._list_widget.itemAt(position)
        entry = self._entry_from_item(item)
        is_valid, _message = validate_score_edit_entry(entry)
        if is_valid is False:
            return

        self._list_widget.setCurrentItem(item)
        menu = QMenu(self._list_widget)
        edit_action = menu.addAction("Изменить оценку")
        delete_action = menu.addAction("Удалить запись")
        chosen_action = menu.exec(self._list_widget.viewport().mapToGlobal(position))
        if chosen_action is edit_action:
            self._edit_user_score(entry)
        elif chosen_action is delete_action:
            self._delete_watched_entry(entry)

    def _delete_watched_entry(self, entry: WatchedEntry | None) -> None:
        is_valid, message = validate_score_edit_entry(entry)
        if is_valid is False:
            self.statusBar().showMessage(message, 4000)
            return

        dataset_key, _movie, _card = entry
        preview = load_delete_preview(dataset_key)
        if preview is None:
            self.statusBar().showMessage("Запись не найдена", 4000)
            return

        dialog = WatchedDeleteDialog(preview, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        result = execute_watched_delete(dataset_key)
        if result.get("ok"):
            self._refresh_after_delete(result)
            return

        self.statusBar().showMessage(format_delete_status_message(result), 4000)

    def _reload_genre_filter_options(self) -> None:
        current = self._selected_genre_filter()
        self._genre_combo.blockSignals(True)
        self._genre_combo.clear()
        self._genre_combo.addItem(GENRE_FILTER_ALL, None)
        for genre in get_available_genres(self._entries):
            self._genre_combo.addItem(genre, genre)
        if current is not None:
            index = self._genre_combo.findData(current)
            self._genre_combo.setCurrentIndex(index if index >= 0 else 0)
        else:
            self._genre_combo.setCurrentIndex(0)
        self._genre_combo.blockSignals(False)

    def _refresh_after_delete(self, result: dict) -> None:
        previous_row = self._list_widget.currentRow()
        self._entries = load_watched_entries()
        self._analytics_view.update_entries(self._entries)
        self._model_view.refresh()
        self._reload_genre_filter_options()
        self._refresh_list()

        if self._list_widget.count() > 0:
            row_to_select = min(max(previous_row, 0), self._list_widget.count() - 1)
            self._list_widget.blockSignals(True)
            self._list_widget.setCurrentRow(row_to_select)
            self._list_widget.blockSignals(False)
            self._detail_card.show_entry(self._visible_entries[row_to_select])
        else:
            self._show_empty_details()

        self.statusBar().showMessage(format_delete_status_message(result), 4000)

    def _edit_user_score(self, entry: WatchedEntry | None) -> None:
        is_valid, message = validate_score_edit_entry(entry)
        if is_valid is False:
            self.statusBar().showMessage(message, 4000)
            return

        score = self._show_user_score_dialog(entry)
        if score is None:
            return

        dataset_key, _movie, _card = entry
        result = save_watched_user_score(dataset_key, score)
        if result.ok and result.reason in ("updated", "nothing_changed"):
            self._refresh_after_user_score_save(dataset_key, result)
            return

        self.statusBar().showMessage(format_save_user_score_status(result), 4000)

    def _show_user_score_dialog(self, entry: WatchedEntry) -> float | None:
        dialog = ScoreEditDialog(entry, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.score_value()

    def _on_filters_changed(self) -> None:
        self._sort_key = self._sort_combo.currentData()
        previous_key = self._current_entry_key()
        self._refresh_list()

        row_to_select = 0
        if previous_key is not None:
            for index, (key, _, _) in enumerate(self._visible_entries):
                if key == previous_key:
                    row_to_select = index
                    break
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(row_to_select)

    def _refresh_list(self) -> None:
        query = self._search_input.text()
        min_score, max_score = self._score_filter_range()
        year_from, year_to = self._year_filter_range()
        genre = self._selected_genre_filter()
        self._visible_entries = apply_view(
            self._entries,
            query,
            self._sort_key,
            min_score,
            max_score,
            year_from,
            year_to,
            genre,
        )

        self._list_widget.blockSignals(True)
        self._list_widget.clear()
        for entry in self._visible_entries:
            _, _, card = entry
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(format_list_label(card))
            self._list_widget.addItem(item)
        self._list_widget.blockSignals(False)

        if self._list_widget.count() == 0:
            self._show_empty_details()
        self._update_list_status()

    def _update_list_status(self) -> None:
        visible = len(self._visible_entries)
        total = len(self._entries)
        query = self._search_input.text()
        score_active = self._score_filter_active()
        year_active = self._year_filter_active()
        genre_active = self._genre_filter_active()
        self._list_counter_label.setText(
            format_watched_list_counter(
                visible,
                total,
                query,
                score_active,
                year_active,
                genre_active,
            )
        )
        self.statusBar().showMessage(
            format_watched_list_status(
                visible,
                total,
                query,
                score_active,
                year_active,
                genre_active,
            )
        )
        self._update_filter_toggle_label()

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._visible_entries):
            self._show_empty_details()
            return
        self._detail_card.show_entry(self._visible_entries[row])

    def _show_empty_details(self) -> None:
        if self._search_input.text().strip():
            title = "Ничего не найдено"
        else:
            title = "Выберите тайтл слева"
        self._detail_card.show_empty(title)


def _prepare_webengine() -> None:
    """Prepare Qt WebEngine before QApplication is created."""
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    try:
        from PyQt6 import QtWebEngineWidgets  # noqa: F401
    except ImportError:
        pass


def main() -> None:
    _prepare_webengine()
    app = QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, 10))
    window = WatchedMoviesWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
