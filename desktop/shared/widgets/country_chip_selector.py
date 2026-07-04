"""Toggleable country chips with wrapping flow layout for filter UI."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from desktop.shared.widgets.collapsible_chip_helpers import (
    ChipExpandControl,
    order_keys_by_checked,
    reorder_flow_layout,
)
from desktop.shared.widgets.genre_chip_selector import FlowLayout


def _normalize_selected_codes(codes) -> list[str]:
    if isinstance(codes, str):
        codes = [codes]
    if not isinstance(codes, (list, tuple, set)):
        return []
    normalized: list[str] = []
    for code in codes:
        text = str(code or "").strip()
        if text:
            normalized.append(text)
    return normalized


class CountryChipSelector(QWidget):
    """Multi-select country filter as compact toggle chips; empty selection means all countries."""

    selection_changed = pyqtSignal()

    def __init__(
        self,
        options: list[dict],
        *,
        object_name: str = "candidateSearchCountries",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._options: list[dict] = []
        self._codes_in_order: list[str] = []
        self._chips: dict[str, QPushButton] = {}
        self._expand = ChipExpandControl()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        self._count_label = QLabel("Все страны")
        self._count_label.setObjectName("countryChipCount")
        self._clear_button = QPushButton("Все страны")
        self._clear_button.setObjectName("countryChipClear")
        self._clear_button.setFlat(True)
        self._clear_button.clicked.connect(self.clear_selection)
        header.addWidget(self._count_label)
        header.addStretch()
        header.addWidget(self._clear_button)
        root.addLayout(header)

        self._chips_host = QWidget()
        self._chips_host.setObjectName("countryChipHost")
        self._flow = FlowLayout(self._chips_host, margin=0, h_spacing=8, v_spacing=8)
        self._chips_host.setLayout(self._flow)
        root.addWidget(self._chips_host)

        expand_button = self._expand.create_button()
        expand_button.clicked.connect(self._toggle_expanded)
        root.addWidget(expand_button)

        self.set_options(options)

    def set_options(self, options: list[dict], selected_codes=None) -> None:
        """Rebuild chips for the given country list and selection."""
        self._expand.reset()
        self._options = [
            {
                "code": str(option.get("code") or "").strip(),
                "label": str(option.get("label") or option.get("code") or "").strip(),
            }
            for option in options
            if str(option.get("code") or "").strip()
        ]
        selected = set(_normalize_selected_codes(selected_codes))
        self._clear_layout()

        for option in self._options:
            code = option["code"]
            label = option["label"]
            chip = QPushButton(label)
            chip.setObjectName("countryFilterChip")
            chip.setCheckable(True)
            chip.setChecked(code in selected)
            chip.setMinimumHeight(36)
            chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            chip.toggled.connect(self._on_chip_toggled)
            self._chips[code] = chip
            self._codes_in_order.append(code)
            self._flow.addWidget(chip)

        self._refresh_chip_layout()

    def set_selected_codes(self, codes) -> None:
        """Update chip selection without rebuilding; empty means all countries."""
        selected = set(_normalize_selected_codes(codes))
        for code in self._codes_in_order:
            chip = self._chips.get(code)
            if chip is None:
                continue
            chip.blockSignals(True)
            chip.setChecked(code in selected if selected else False)
            chip.blockSignals(False)
        self._refresh_chip_layout()

    def selected_country_codes(self) -> list[str]:
        """Return selected ISO codes; empty list means all countries."""
        return [
            code
            for code in order_keys_by_checked(self._codes_in_order, self._chips)
            if self._chips.get(code) and self._chips[code].isChecked()
        ]

    def is_all_selected(self) -> bool:
        return len(self.selected_country_codes()) == 0

    def clear_selection(self) -> None:
        for chip in self._chips.values():
            chip.blockSignals(True)
            chip.setChecked(False)
            chip.blockSignals(False)
        self._refresh_chip_layout()

    def _ordered_chips(self) -> list[QPushButton]:
        return [
            self._chips[code]
            for code in order_keys_by_checked(self._codes_in_order, self._chips)
            if code in self._chips
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
        self._codes_in_order.clear()
        while self._flow.count():
            item = self._flow.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _update_count_label(self, *_args, emit_selection: bool = True) -> None:
        count = len(self.selected_country_codes())
        self._count_label.setText("Все страны" if count == 0 else f"Выбрано: {count}")
        if emit_selection:
            self.selection_changed.emit()
