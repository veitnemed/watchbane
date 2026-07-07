"""Shared expand/collapse behavior for chip filter selectors."""

from __future__ import annotations

from PyQt6.QtWidgets import QPushButton

from desktop.i18n import tr

COLLAPSED_VISIBLE_CHIP_COUNT = 5


class ChipExpandControl:
    """Show the first N chips; expand to reveal the rest on demand."""

    def __init__(
        self,
        *,
        visible_count: int = COLLAPSED_VISIBLE_CHIP_COUNT,
        expand_object_name: str = "chipExpandToggle",
    ) -> None:
        self.visible_count = visible_count
        self.expanded = False
        self._expand_object_name = expand_object_name
        self._button: QPushButton | None = None
        self._total = 0
        self._hidden_count = 0

    def create_button(self) -> QPushButton:
        button = QPushButton()
        button.setObjectName(self._expand_object_name)
        button.setFlat(True)
        self._button = button
        return button

    def reset(self) -> None:
        self.expanded = False

    def toggle(self) -> None:
        self.expanded = not self.expanded

    def apply_visibility(self, chips: list[QPushButton]) -> None:
        self._total = len(chips)
        hidden_count = 0
        for index, chip in enumerate(chips):
            should_show = self.expanded or index < self.visible_count
            chip.setVisible(should_show)
            if not should_show:
                hidden_count += 1
        self._hidden_count = hidden_count

        self._update_button()

    def _update_button(self) -> None:
        if self._button is None:
            return
        has_collapsible_items = self._total > self.visible_count
        self._button.setVisible(has_collapsible_items)
        if not has_collapsible_items:
            return
        if self.expanded:
            self._button.setText(tr("common.chips.collapse"))
        else:
            self._button.setText(tr("common.chips.show_more", count=self._hidden_count))


def order_keys_by_checked(base_keys: list[str], chips: dict[str, QPushButton]) -> list[str]:
    """Return selected keys first, preserving the original popularity order inside each group."""
    selected: list[str] = []
    unselected: list[str] = []
    for key in base_keys:
        chip = chips.get(key)
        if chip is None:
            continue
        if chip.isChecked():
            selected.append(key)
        else:
            unselected.append(key)
    return selected + unselected


def reorder_flow_layout(layout, widgets: list[QPushButton]) -> None:
    """Reorder an existing FlowLayout without recreating chip widgets."""
    items_by_widget = {}
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            items_by_widget[widget] = item

    for widget in widgets:
        item = items_by_widget.pop(widget, None)
        if item is not None:
            layout.addItem(item)

    for item in items_by_widget.values():
        layout.addItem(item)
