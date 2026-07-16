"""One-shot profile selector shown after a deferred full reset."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.use_cases import profile_management
from desktop.theme.scaling import scale_px


class ProfileSelectionDialog(QDialog):
    """Choose or create a profile before its SQLite runtime is initialized."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("startupProfileSelector")
        self.setWindowTitle("Watchbane — выбор профиля")
        self.setModal(True)
        self.setMinimumWidth(scale_px(460))
        self._selected_profile: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("Выберите профиль")
        title.setObjectName("startupProfileSelectorTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        description = QLabel(
            "Сброс завершён. Выберите существующий профиль или создайте новый."
        )
        description.setObjectName("startupProfileSelectorDescription")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description)

        self._profiles = QComboBox()
        self._profiles.setObjectName("startupProfileCombo")
        layout.addWidget(self._profiles)

        actions = QHBoxLayout()
        self._create_button = QPushButton("Создать профиль")
        self._create_button.setObjectName("startupProfileCreateButton")
        self._continue_button = QPushButton("Продолжить")
        self._continue_button.setObjectName("startupProfileContinueButton")
        self._create_button.clicked.connect(self._create_profile)
        self._continue_button.clicked.connect(self._accept_selection)
        actions.addWidget(self._create_button)
        actions.addStretch(1)
        actions.addWidget(self._continue_button)
        layout.addLayout(actions)

        self._reload_profiles()

    @property
    def selected_profile(self) -> str | None:
        return self._selected_profile

    def _reload_profiles(self, *, select_name: str | None = None) -> None:
        self._profiles.clear()
        selected_index = 0
        for index, item in enumerate(profile_management.list_profile_descriptions()):
            name = item["name"]
            label = item["display_name"]
            if name == profile_management.MAIN_PROFILE:
                label = f"{label} (основной)"
            self._profiles.addItem(label, name)
            if name == select_name or (select_name is None and item["active"] == "1"):
                selected_index = index
        self._profiles.setCurrentIndex(selected_index)
        self._continue_button.setEnabled(self._profiles.count() > 0)

    def _create_profile(self) -> None:
        display_name, accepted = QInputDialog.getText(
            self,
            "Новый профиль",
            "Название профиля:",
        )
        if accepted is False or not display_name.strip():
            return
        try:
            created = profile_management.create_profile(
                display_name,
                display_name=display_name,
            )
        except (ValueError, OSError, RuntimeError) as error:
            QMessageBox.warning(
                self,
                "Профиль не создан",
                f"Не удалось создать профиль.\n\n{error}",
            )
            return
        self._reload_profiles(select_name=created)

    def _accept_selection(self) -> None:
        selected = self._profiles.currentData()
        if selected in (None, ""):
            return
        self._selected_profile = str(selected)
        self.accept()
