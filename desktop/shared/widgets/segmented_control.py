"""Small exclusive segmented selector used by recommendation controls."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from desktop.theme.scaling import control_px


class SegmentedControl(QWidget):
    valueChanged = pyqtSignal(str)

    def __init__(self, options: list[tuple[str, str]] | tuple[tuple[str, str], ...], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("segmentedControl")
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for index, (label, value) in enumerate(options):
            button = QPushButton(str(label), self)
            button.setObjectName("segmentedControlButton")
            button.setCheckable(True)
            button.setProperty("segmentPosition", "first" if index == 0 else "last" if index == len(options) - 1 else "middle")
            button.setMinimumHeight(control_px(34))
            self._group.addButton(button)
            self._buttons[str(value)] = button
            layout.addWidget(button, 1)
            button.clicked.connect(lambda _checked=False, current=str(value): self.valueChanged.emit(current))
        if self._buttons:
            next(iter(self._buttons.values())).setChecked(True)

    def value(self) -> str:
        for value, button in self._buttons.items():
            if button.isChecked():
                return value
        return next(iter(self._buttons), "")

    def setValue(self, value: str) -> None:
        button = self._buttons.get(str(value))
        if button is not None:
            button.setChecked(True)

    def buttons(self) -> tuple[QPushButton, ...]:
        return tuple(self._buttons.values())
