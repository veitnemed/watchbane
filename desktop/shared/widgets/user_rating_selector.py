"""Reusable three-choice user reaction selector."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from dataset.models.user_rating import UserRating, normalize_user_rating
from desktop.i18n import tr
from desktop.theme.scaling import control_px
from desktop.theme.styles.shared_widgets import build_user_rating_selector_style


class UserRatingSelector(QWidget):
    valueChanged = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("userRatingSelector")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(build_user_rating_selector_style())
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[int, QPushButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(control_px(8))
        image_dir = Path(__file__).resolve().parents[2] / "images"
        options = (
            (UserRating.NOT_FOR_ME, "user_rating.not_for_me", image_dir / "user_rating_not_for_me.svg"),
            (UserRating.OK, "user_rating.ok", image_dir / "user_rating_ok.svg"),
            (UserRating.TOP, "user_rating.top", image_dir / "user_rating_top.svg"),
        )
        for rating, label_key, icon_path in options:
            label = tr(label_key)
            button = QPushButton(QIcon(str(icon_path)), label, self)
            button.setObjectName("userRatingButton")
            button.setCheckable(True)
            button.setAccessibleName(label)
            button.setToolTip(tr(f"{label_key}.tooltip"))
            button.setIconSize(QSize(control_px(22), control_px(22)))
            button.setMinimumWidth(control_px(118))
            self._group.addButton(button, int(rating))
            self._buttons[int(rating)] = button
            layout.addWidget(button, 1)
        self._group.idClicked.connect(lambda value: self.valueChanged.emit(int(value)))
        self._shortcuts: list[QShortcut] = []
        for value in (1, 2, 3):
            shortcut = QShortcut(QKeySequence(str(value)), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda rating=value: self.setValue(rating))
            self._shortcuts.append(shortcut)

    def value(self) -> int | None:
        checked = self._group.checkedId()
        return checked if checked in self._buttons else None

    def buttons(self) -> tuple[QPushButton, ...]:
        return tuple(self._buttons[value] for value in sorted(self._buttons))

    def setValue(self, value: int | None) -> None:
        normalized = normalize_user_rating(value)
        if normalized is None:
            self.clear()
            return
        changed = self.value() != normalized
        self._buttons[normalized].setChecked(True)
        if changed:
            self.valueChanged.emit(normalized)

    def clear(self) -> None:
        had_value = self.value() is not None
        self._group.setExclusive(False)
        for button in self._buttons.values():
            button.setChecked(False)
        self._group.setExclusive(True)
        if had_value:
            self.valueChanged.emit(None)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3):
            self.setValue(int(event.text()))
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_Right, Qt.Key.Key_Down):
            current = self.value() or int(UserRating.OK)
            delta = -1 if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up) else 1
            self.setValue(max(1, min(3, current + delta)))
            event.accept()
            return
        super().keyPressEvent(event)
