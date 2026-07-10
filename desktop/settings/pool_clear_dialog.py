"""Typed confirmation dialog for clearing the common candidate pool."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from desktop.i18n import get_interface_language, tr
from desktop.theme import build_delete_dialog_style
from desktop.theme.scaling import layout_px


def pool_clear_confirmation_text() -> str:
    """Return the typed confirmation token for the active interface language."""
    if get_interface_language() == "en":
        return "CLEAR"
    return "ОЧИСТИТЬ"


def is_pool_clear_confirmation_valid(text: str) -> bool:
    return str(text or "").strip() == pool_clear_confirmation_text()


POOL_CLEAR_DIALOG_STYLE = build_delete_dialog_style()


class PoolClearDialog(QDialog):
    """Confirmation dialog with typed CLEAR / ОЧИСТИТЬ confirmation."""

    def __init__(self, unique_total: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("poolClearDialog")
        self.setWindowTitle(tr("settings.pool.ops.clear.dialog.title"))
        self.setModal(True)
        self.setFixedWidth(layout_px(430))
        self.setStyleSheet(POOL_CLEAR_DIALOG_STYLE)

        confirmation = pool_clear_confirmation_text()
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            layout_px(14),
            layout_px(14),
            layout_px(14),
            layout_px(14),
        )
        root_layout.setSpacing(0)

        card_frame = QFrame()
        card_frame.setObjectName("deleteRecordCard")
        root_layout.addWidget(card_frame)

        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(
            layout_px(18),
            layout_px(18),
            layout_px(18),
            layout_px(18),
        )
        card_layout.setSpacing(layout_px(12))

        header = QLabel(tr("settings.pool.ops.clear.dialog.title"))
        header.setObjectName("deleteRecordTitle")
        card_layout.addWidget(header)

        warning = QLabel(tr("settings.pool.ops.clear.dialog.warning", count=unique_total))
        warning.setObjectName("deleteRecordWarning")
        warning.setWordWrap(True)
        card_layout.addWidget(warning)

        confirm_label = QLabel(
            tr("settings.pool.ops.clear.dialog.confirm_label", confirmation=confirmation)
        )
        confirm_label.setObjectName("deleteRecordFieldLabel")
        card_layout.addWidget(confirm_label)

        self._confirm_input = QLineEdit()
        self._confirm_input.setObjectName("deleteRecordConfirmInput")
        self._confirm_input.setPlaceholderText(confirmation)
        self._confirm_input.textChanged.connect(self._update_confirm_button_state)
        card_layout.addWidget(self._confirm_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        confirm_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if confirm_button is not None:
            confirm_button.setObjectName("deleteRecordConfirmButton")
            confirm_button.setText(tr("settings.pool.ops.clear.dialog.confirm"))
            confirm_button.setEnabled(False)
            confirm_button.setAutoDefault(False)
        if cancel_button is not None:
            cancel_button.setText(tr("common.cancel"))
            cancel_button.setAutoDefault(False)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        card_layout.addWidget(buttons)

        self._confirm_button = confirm_button
        self._confirm_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _update_confirm_button_state(self, _text: str = "") -> None:
        if self._confirm_button is not None:
            self._confirm_button.setEnabled(is_pool_clear_confirmation_valid(self._confirm_input.text()))

    def _on_accept(self) -> None:
        if is_pool_clear_confirmation_valid(self._confirm_input.text()) is False:
            return
        self.accept()
