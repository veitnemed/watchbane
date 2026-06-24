"""PyQt6 read-only desktop viewer for watched movies and series."""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from desktop.watched_view import (
    SORT_OPTIONS,
    WatchedEntry,
    apply_view,
    format_list_label,
    load_watched_entries,
    resolve_local_poster_path,
)

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1b1b1f;
    color: #e8e8ea;
}
QLineEdit, QComboBox {
    background-color: #2a2a31;
    border: 1px solid #3a3a44;
    border-radius: 6px;
    padding: 8px 10px;
    color: #f0f0f2;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #2a2a31;
    color: #f0f0f2;
    selection-background-color: #3d5afe;
}
QListWidget {
    background-color: #222228;
    border: 1px solid #3a3a44;
    border-radius: 8px;
    padding: 4px;
}
QListWidget::item {
    padding: 10px 12px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #3d5afe;
    color: #ffffff;
}
QListWidget::item:hover {
    background-color: #2f3340;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QFrame#detailCard {
    background-color: #222228;
    border: 1px solid #3a3a44;
    border-radius: 12px;
}
"""


class WatchedMoviesWindow(QMainWindow):
    """Main read-only window for browsing watched titles."""

    def __init__(self) -> None:
        super().__init__()
        self._entries: list[WatchedEntry] = load_watched_entries()
        self._visible_entries: list[WatchedEntry] = list(self._entries)
        self._sort_key = SORT_OPTIONS[0][0]

        self.setWindowTitle("Terminal Movies Learn Desktop")
        self.resize(1180, 720)
        self.setStyleSheet(DARK_STYLE)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
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

        self._refresh_list()
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Поиск по названию")
        self._search_input.textChanged.connect(self._on_filters_changed)
        layout.addWidget(self._search_input)

        self._sort_combo = QComboBox()
        for sort_key, label in SORT_OPTIONS:
            self._sort_combo.addItem(label, sort_key)
        self._sort_combo.currentIndexChanged.connect(self._on_filters_changed)
        layout.addWidget(self._sort_combo)

        self._list_widget = QListWidget()
        self._list_widget.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list_widget, stretch=1)

        return panel

    def _build_right_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        card = QFrame()
        card.setObjectName("detailCard")
        self._detail_layout = QVBoxLayout(card)
        self._detail_layout.setContentsMargins(24, 24, 24, 24)
        self._detail_layout.setSpacing(14)

        self._poster_label = QLabel("Нет постера")
        self._poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster_label.setFixedSize(220, 330)
        self._poster_label.setStyleSheet(
            "background-color: #2f2f36; border-radius: 10px; color: #9a9aa3;"
        )

        self._title_label = QLabel("Выберите тайтл слева")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        self._title_label.setWordWrap(True)

        self._user_score_label = QLabel("—")
        score_font = QFont()
        score_font.setPointSize(42)
        score_font.setBold(True)
        self._user_score_label.setFont(score_font)
        self._user_score_label.setStyleSheet("color: #ffd166;")

        self._meta_label = QLabel("")
        self._meta_label.setWordWrap(True)
        self._meta_label.setStyleSheet("color: #c7c7d0;")

        self._genres_label = QLabel("")
        self._genres_label.setWordWrap(True)

        self._country_label = QLabel("")
        self._country_label.setWordWrap(True)

        self._overview_label = QLabel("")
        self._overview_label.setWordWrap(True)
        self._overview_label.setStyleSheet("color: #d8d8de;")

        self._detail_layout.addWidget(self._poster_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self._detail_layout.addWidget(self._title_label)
        self._detail_layout.addWidget(self._user_score_label)
        self._detail_layout.addWidget(self._meta_label)
        self._detail_layout.addWidget(self._genres_label)
        self._detail_layout.addWidget(self._country_label)
        self._detail_layout.addWidget(self._overview_label)
        self._detail_layout.addStretch()

        scroll.setWidget(card)
        return scroll

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

    def _current_entry_key(self) -> str | None:
        row = self._list_widget.currentRow()
        if row < 0 or row >= len(self._visible_entries):
            return None
        return self._visible_entries[row][0]

    def _refresh_list(self) -> None:
        query = self._search_input.text()
        self._visible_entries = apply_view(self._entries, query, self._sort_key)

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

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._visible_entries):
            self._show_empty_details()
            return
        self._show_entry(self._visible_entries[row])

    def _show_empty_details(self) -> None:
        self._poster_label.setPixmap(QPixmap())
        self._poster_label.setText("Нет постера")
        self._title_label.setText("Ничего не найдено" if self._search_input.text().strip() else "Выберите тайтл слева")
        self._user_score_label.setText("—")
        self._meta_label.setText("")
        self._genres_label.setText("")
        self._country_label.setText("")
        self._overview_label.setText("")

    def _show_entry(self, entry: WatchedEntry) -> None:
        _, movie, card = entry
        self._title_label.setText(card.get("title") or entry[0])

        user_score = card.get("user_score")
        self._user_score_label.setText("—" if user_score is None else f"{user_score:g}")

        year = card.get("year")
        imdb = card.get("imdb_score")
        kp = card.get("kp_score")
        meta_parts = []
        if year is not None:
            meta_parts.append(f"Год: {year}")
        if imdb is not None:
            meta_parts.append(f"IMDb: {imdb:g}")
        if kp is not None:
            meta_parts.append(f"КП: {kp:g}")
        self._meta_label.setText("  ·  ".join(meta_parts))

        genres = card.get("genres") or []
        self._genres_label.setText(f"Жанры: {', '.join(genres)}" if genres else "Жанры: —")

        country = card.get("country")
        self._country_label.setText(f"Страна: {country}" if country else "Страна: —")

        overview = card.get("overview")
        self._overview_label.setText(overview if overview else "Описание отсутствует.")

        poster_path = resolve_local_poster_path(movie, card)
        if poster_path is not None:
            pixmap = QPixmap(poster_path)
            if pixmap.isNull() is False:
                scaled = pixmap.scaled(
                    self._poster_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._poster_label.setText("")
                self._poster_label.setPixmap(scaled)
                return

        self._poster_label.setPixmap(QPixmap())
        self._poster_label.setText("Нет постера")


def main() -> None:
    app = QApplication(sys.argv)
    window = WatchedMoviesWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
