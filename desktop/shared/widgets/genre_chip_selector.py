"""Toggleable genre chips with wrapping flow layout for filter UI."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, QRect, pyqtSignal
from PyQt6.QtWidgets import QLabel, QLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from desktop.i18n import tr
from desktop.shared.widgets.collapsible_chip_helpers import (
    ChipExpandControl,
    order_keys_by_checked,
    reorder_flow_layout,
)
from desktop.theme.scaling import layout_px


class FlowLayout(QLayout):
    """Simple left-to-right layout that wraps items to the next row."""

    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 6, v_spacing: int = 6) -> None:
        super().__init__(parent)
        self._item_list: list = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item) -> None:
        self._item_list.append(item)

    def count(self) -> int:
        return len(self._item_list)

    def itemAt(self, index: int):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._item_list:
            widget = item.widget()
            if widget is None:
                continue
            space_x = self._h_spacing
            space_y = self._v_spacing
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y += line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(x, y, item.sizeHint().width(), item.sizeHint().height()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + margins.bottom()


class GenreChipSelector(QWidget):
    """Multi-select genre filter as compact toggle chips."""

    selection_changed = pyqtSignal()

    def __init__(self, parent=None, *, object_name: str = "genreChipSelector") -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._genres: list[str] = []
        self._chips: dict[str, QPushButton] = {}
        self._expand = ChipExpandControl()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(layout_px(8))

        self._count_label = QLabel(tr("common.selected_count", count=0))
        self._count_label.setObjectName("genreChipCount")
        root.addWidget(self._count_label)

        self._chips_host = QWidget()
        self._chips_host.setObjectName("genreChipHost")
        self._flow = FlowLayout(self._chips_host, margin=0, h_spacing=8, v_spacing=8)
        self._chips_host.setLayout(self._flow)
        root.addWidget(self._chips_host)

        expand_button = self._expand.create_button()
        expand_button.clicked.connect(self._toggle_expanded)
        root.addWidget(expand_button)

    def set_options(self, genres: list[str], selected: list[str] | None = None) -> None:
        """Rebuild chips for the given genre list and selection."""
        self._expand.reset()
        selected_normalized = {str(value).casefold() for value in (selected or [])}
        self._genres = [str(genre).strip() for genre in genres if str(genre).strip()]
        self._clear_layout()

        for genre in self._genres:
            chip = QPushButton(genre)
            chip.setObjectName("genreFilterChip")
            chip.setCheckable(True)
            chip.setChecked(genre.casefold() in selected_normalized)
            chip.setMinimumHeight(layout_px(34))
            chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            chip.toggled.connect(self._on_chip_toggled)
            self._chips[genre] = chip
            self._flow.addWidget(chip)

        self._refresh_chip_layout()

    def selected_genres(self) -> list[str]:
        """Return selected genre labels in display order."""
        return [
            genre
            for genre in order_keys_by_checked(self._genres, self._chips)
            if self._chips.get(genre) and self._chips[genre].isChecked()
        ]

    def clear_selection(self) -> None:
        for chip in self._chips.values():
            chip.blockSignals(True)
            chip.setChecked(False)
            chip.blockSignals(False)
        self._refresh_chip_layout()

    def _ordered_chips(self) -> list[QPushButton]:
        return [
            self._chips[genre]
            for genre in order_keys_by_checked(self._genres, self._chips)
            if genre in self._chips
        ]

    def _toggle_expanded(self) -> None:
        self._expand.toggle()
        self._refresh_chip_layout(update_count_only=True)

    def _on_chip_toggled(self, *_args) -> None:
        self._refresh_chip_layout()

    def _refresh_chip_layout(self, *, update_count_only: bool = False) -> None:
        ordered_chips = self._ordered_chips()
        reorder_flow_layout(self._flow, ordered_chips)
        self._expand.apply_visibility(ordered_chips)
        self._chips_host.adjustSize()
        self._update_count_label(emit_selection=not update_count_only)

    def _clear_layout(self) -> None:
        self._chips.clear()
        while self._flow.count():
            item = self._flow.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _update_count_label(self, *_args, emit_selection: bool = True) -> None:
        count = len(self.selected_genres())
        self._count_label.setText(tr("common.selected_count", count=count))
        if emit_selection:
            self.selection_changed.emit()
