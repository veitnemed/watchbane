"""PyQt6 desktop viewer for watched movies and series."""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
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
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.analytics_view import AnalyticsView
from desktop.theme import FONT_FAMILY, build_app_style, build_score_edit_dialog_style
from desktop.watched_view import (
    SORT_OPTIONS,
    USER_SCORE_MAX,
    USER_SCORE_MIN,
    USER_SCORE_STEP,
    WatchedDetailCard,
    WatchedEntry,
    apply_view,
    format_list_label,
    format_save_user_score_status,
    format_user_score_display,
    format_watched_list_status,
    get_user_score_spin_value,
    load_watched_entries,
    save_watched_user_score,
    validate_score_edit_entry,
)

DARK_STYLE = build_app_style()
SCORE_EDIT_DIALOG_STYLE = build_score_edit_dialog_style()


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
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        tabs.addTab(watched_tab, "Watched")
        self._analytics_view = AnalyticsView(self._entries)
        tabs.addTab(self._analytics_view.widget, "Аналитика")

        self._refresh_list()
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("watchedSearch")
        self._search_input.setPlaceholderText("Поиск по названию")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._on_filters_changed)
        layout.addWidget(self._search_input)

        self._sort_combo = QComboBox()
        self._sort_combo.setObjectName("watchedSort")
        for sort_key, label in SORT_OPTIONS:
            self._sort_combo.addItem(label, sort_key)
        self._sort_combo.currentIndexChanged.connect(self._on_filters_changed)
        layout.addWidget(self._sort_combo)

        layout.addWidget(self._build_score_filter_panel())

        self._list_widget = QListWidget()
        self._list_widget.setObjectName("watchedList")
        self._list_widget.setSpacing(2)
        self._list_widget.setUniformItemSizes(True)
        self._list_widget.currentRowChanged.connect(self._on_selection_changed)
        self._list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_widget.customContextMenuRequested.connect(self._open_list_context_menu)
        layout.addWidget(self._list_widget, stretch=1)

        return panel

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

        reset_button = QPushButton("Сбросить")
        reset_button.setObjectName("watchedScoreReset")
        reset_button.clicked.connect(self._reset_score_filter)
        header_row.addWidget(reset_button)
        layout.addLayout(header_row)

        score_row = QHBoxLayout()
        score_row.setContentsMargins(0, 0, 0, 0)
        score_row.setSpacing(6)

        min_label = QLabel("от")
        min_label.setObjectName("watchedScoreFilterLabel")
        score_row.addWidget(min_label)
        self._score_min_input = QDoubleSpinBox()
        self._score_min_input.setObjectName("watchedScoreMin")
        self._configure_score_filter_spinbox(self._score_min_input, USER_SCORE_MIN)
        self._score_min_input.valueChanged.connect(self._on_score_min_changed)
        score_row.addWidget(self._score_min_input)

        max_label = QLabel("до")
        max_label.setObjectName("watchedScoreFilterLabel")
        score_row.addWidget(max_label)
        self._score_max_input = QDoubleSpinBox()
        self._score_max_input.setObjectName("watchedScoreMax")
        self._configure_score_filter_spinbox(self._score_max_input, USER_SCORE_MAX)
        self._score_max_input.valueChanged.connect(self._on_score_max_changed)
        score_row.addWidget(self._score_max_input)
        layout.addLayout(score_row)
        return frame

    def _configure_score_filter_spinbox(self, spinbox: QDoubleSpinBox, value: float) -> None:
        spinbox.setRange(USER_SCORE_MIN, USER_SCORE_MAX)
        spinbox.setSingleStep(USER_SCORE_STEP)
        spinbox.setDecimals(1)
        spinbox.setValue(value)

    def _score_filter_range(self) -> tuple[float, float]:
        return (self._score_min_input.value(), self._score_max_input.value())

    def _score_filter_active(self) -> bool:
        min_score, max_score = self._score_filter_range()
        return min_score > USER_SCORE_MIN or max_score < USER_SCORE_MAX

    def _on_score_min_changed(self, value: float) -> None:
        if value > self._score_max_input.value():
            self._score_max_input.blockSignals(True)
            self._score_max_input.setValue(value)
            self._score_max_input.blockSignals(False)
        self._on_filters_changed()

    def _on_score_max_changed(self, value: float) -> None:
        if value < self._score_min_input.value():
            self._score_min_input.blockSignals(True)
            self._score_min_input.setValue(value)
            self._score_min_input.blockSignals(False)
        self._on_filters_changed()

    def _reset_score_filter(self) -> None:
        self._score_min_input.blockSignals(True)
        self._score_max_input.blockSignals(True)
        self._score_min_input.setValue(USER_SCORE_MIN)
        self._score_max_input.setValue(USER_SCORE_MAX)
        self._score_min_input.blockSignals(False)
        self._score_max_input.blockSignals(False)
        self._on_filters_changed()

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
        chosen_action = menu.exec(self._list_widget.viewport().mapToGlobal(position))
        if chosen_action is edit_action:
            self._edit_user_score(entry)

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
        self._visible_entries = apply_view(self._entries, query, self._sort_key, min_score, max_score)

        self._list_widget.blockSignals(True)
        self._list_widget.clear()
        for entry in self._visible_entries:
            _, _, card = entry
            item = QListWidgetItem(format_list_label(card))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._list_widget.addItem(item)
        self._list_widget.blockSignals(False)

        if self._list_widget.count() == 0:
            self._show_empty_details()
        self._update_list_status()

    def _update_list_status(self) -> None:
        visible = len(self._visible_entries)
        total = len(self._entries)
        self.statusBar().showMessage(
            format_watched_list_status(visible, total, self._search_input.text(), self._score_filter_active())
        )

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
