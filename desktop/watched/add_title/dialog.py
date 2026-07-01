"""Add-title flow: separate search and preview dialogs."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from candidates.tmdb_country_options import add_title_country_combo_options
from common import valid
from config import constant
from config import scheme
from dataset.add_title_service import (
    AddTitleResolveBundle,
    build_candidate_transfer_bundle,
    format_resolve_status_lines,
    save_add_title_record,
)
from desktop.theme import build_add_title_dialog_style
from desktop.watched.add_title.worker import AddTitleResolveWorker
from desktop.shared.detail import (
    ADD_TITLE_PREVIEW_CARD_PROFILE,
    WatchedDetailCard,
)
from desktop.watched.model import (
    USER_SCORE_MAX,
    USER_SCORE_MIN,
    USER_SCORE_STEP,
    YEAR_FILTER_MIN,
    normalize_user_score_value,
)

ADD_TITLE_DIALOG_STYLE = build_add_title_dialog_style()

SEARCH_DIALOG_WIDTH = 520
SEARCH_DIALOG_HEIGHT = 196
SEARCH_DIALOG_HEIGHT_ACTIVE = 236
PREVIEW_DIALOG_WIDTH = 760
PREVIEW_DIALOG_HEIGHT = 620
PREVIEW_CARD_SCROLL_MIN_HEIGHT = 260


class AddTitleSearchDialog(QDialog):
    """Compact dialog: title, country, progress. Closes when resolve succeeds."""

    def __init__(
        self,
        parent=None,
        *,
        initial_title: str = "",
        initial_country: str = "",
    ) -> None:
        super().__init__(parent)
        self._bundle: AddTitleResolveBundle | None = None
        self._worker: AddTitleResolveWorker | None = None
        self.last_title = initial_title.strip()
        self.last_country = initial_country

        self.setObjectName("addTitleSearchDialog")
        self.setWindowTitle("Добавить тайтл — поиск")
        self.setModal(True)
        self.setFixedSize(SEARCH_DIALOG_WIDTH, SEARCH_DIALOG_HEIGHT)
        self.setStyleSheet(ADD_TITLE_DIALOG_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(8)

        header = QLabel("Добавить тайтл")
        header.setObjectName("addTitleHeader")
        root_layout.addWidget(header)

        subtitle = QLabel("Введите название и нажмите «Найти»")
        subtitle.setObjectName("addTitleSubtitle")
        subtitle.setWordWrap(True)
        root_layout.addWidget(subtitle)

        search_frame = QFrame()
        search_frame.setObjectName("addTitleSearchPanel")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(12, 10, 12, 10)
        search_layout.setSpacing(8)

        self._title_input = QLineEdit()
        self._title_input.setObjectName("addTitleSearchInput")
        self._title_input.setPlaceholderText("Название сериала")
        self._title_input.setText(self.last_title)
        self._title_input.returnPressed.connect(self._start_search)

        self._country_combo = QComboBox()
        self._country_combo.setObjectName("addTitleCountryCombo")
        for label, value in add_title_country_combo_options():
            self._country_combo.addItem(label, value)
        self._set_country_selection(initial_country)

        self._search_button = QPushButton("Найти")
        self._search_button.setObjectName("addTitleSearchButton")
        self._search_button.clicked.connect(self._start_search)

        search_layout.addWidget(self._title_input, stretch=3)
        search_layout.addWidget(self._country_combo, stretch=1)
        search_layout.addWidget(self._search_button)
        root_layout.addWidget(search_frame)

        self._progress = QProgressBar()
        self._progress.setObjectName("addTitleProgress")
        self._progress.setTextVisible(True)
        self._progress.hide()
        root_layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setObjectName("addTitleStatus")
        self._status_label.setWordWrap(True)
        self._status_label.hide()
        root_layout.addWidget(self._status_label)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 4, 0, 0)
        footer.addStretch()
        cancel_button = QPushButton("Отмена")
        cancel_button.setObjectName("addTitleSecondaryButton")
        cancel_button.clicked.connect(self.reject)
        footer.addWidget(cancel_button)
        root_layout.addLayout(footer)

        self._title_input.setFocus(Qt.FocusReason.OtherFocusReason)
        if self.last_title:
            self._title_input.selectAll()

    @property
    def resolve_bundle(self) -> AddTitleResolveBundle | None:
        return self._bundle

    def _set_country_selection(self, country: str) -> None:
        normalized = str(country or "").strip()
        if normalized == "":
            self._country_combo.setCurrentIndex(0)
            return
        for index in range(self._country_combo.count()):
            if self._country_combo.itemData(index) == normalized:
                self._country_combo.setCurrentIndex(index)
                return

    def _selected_country(self) -> str:
        country = self._country_combo.currentData()
        if country is None:
            return ""
        return str(country).strip()

    def _set_search_active(self, active: bool) -> None:
        self._title_input.setEnabled(not active)
        self._country_combo.setEnabled(not active)
        self._search_button.setEnabled(not active)
        self._progress.setVisible(active)
        self._status_label.setVisible(active)
        self.setFixedHeight(SEARCH_DIALOG_HEIGHT_ACTIVE if active else SEARCH_DIALOG_HEIGHT)
        if active is False:
            self._progress.reset()

    def _start_search(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        title = self._title_input.text().strip()
        if valid.is_correct_title(title) is False:
            QMessageBox.warning(self, "Добавить тайтл", "Введите корректное название.")
            return

        self.last_title = title
        self.last_country = self._selected_country()
        self._bundle = None
        self._set_search_active(True)
        self._status_label.setText("Поиск…")
        self._progress.setValue(0)
        self._progress.setMaximum(7)

        worker = AddTitleResolveWorker(title, self.last_country, self)
        worker.progress.connect(self._on_progress)
        worker.finished_with_result.connect(self._on_resolve_finished)
        worker.failed.connect(self._on_resolve_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_progress(self, current: int, total: int, message: str) -> None:
        self._progress.setMaximum(max(total, 1))
        self._progress.setValue(min(current, total))
        percent = int(round(100 * current / max(total, 1)))
        self._progress.setFormat(f"{percent}%")
        self._status_label.setText(message)

    def _on_resolve_failed(self, message: str) -> None:
        self._worker = None
        self._set_search_active(False)
        QMessageBox.critical(self, "Добавить тайтл", f"Ошибка поиска:\n{message}")

    def _on_resolve_finished(self, bundle: AddTitleResolveBundle) -> None:
        self._worker = None
        self._set_search_active(False)
        self._bundle = bundle
        self.accept()

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
        super().closeEvent(event)


class AddTitlePreviewDialog(QDialog):
    """Preview card and confirm. Closes on save or «Искать другой»."""

    def __init__(
        self,
        bundle: AddTitleResolveBundle,
        parent=None,
        *,
        transfer_mode: bool = False,
    ) -> None:
        super().__init__(parent)
        self._bundle = bundle
        self._transfer_mode = transfer_mode or bundle.pool_candidate is not None
        self._save_result = None
        self.search_again = False

        self.setObjectName("addTitlePreviewDialog")
        window_title = "Перенос из pool — подтверждение" if self._transfer_mode else "Добавить тайтл — подтверждение"
        self.setWindowTitle(window_title)
        self.setModal(True)
        self.setMinimumWidth(PREVIEW_DIALOG_WIDTH)
        self.resize(PREVIEW_DIALOG_WIDTH, PREVIEW_DIALOG_HEIGHT)
        self.setStyleSheet(ADD_TITLE_DIALOG_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        self._preview_header = QLabel(self._format_preview_header(bundle.preview_card))
        self._preview_header.setObjectName("addTitleHeader")
        root_layout.addWidget(self._preview_header)

        self._warning_label = QLabel("")
        self._warning_label.setObjectName("addTitleWarning")
        self._warning_label.setWordWrap(True)
        self._fill_warning_label()
        root_layout.addWidget(self._warning_label)

        scroll = QScrollArea()
        scroll.setObjectName("addTitlePreviewScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(PREVIEW_CARD_SCROLL_MIN_HEIGHT)

        card_shell = QFrame()
        card_shell.setObjectName("addTitlePreviewCard")
        card_shell_layout = QVBoxLayout(card_shell)
        card_shell_layout.setContentsMargins(10, 10, 10, 10)
        card_shell_layout.setSpacing(0)

        self._detail_card = WatchedDetailCard(card_shell, profile=ADD_TITLE_PREVIEW_CARD_PROFILE)
        card_shell_layout.addWidget(self._detail_card.widget)
        scroll.setWidget(card_shell)
        root_layout.addWidget(scroll, stretch=1)

        confirm_hint = QLabel(
            "Проверьте карточку и укажите только вашу оценку"
            if self._transfer_mode is False
            else "Проверьте карточку и укажите оценку для переноса в watched"
        )
        confirm_hint.setObjectName("addTitleConfirmHint")
        confirm_hint.setWordWrap(True)
        root_layout.addWidget(confirm_hint)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        year_label = QLabel("Год")
        year_label.setObjectName("addTitleFieldLabel")
        self._year_label = QLabel(self._format_resolved_year(bundle))
        self._year_label.setObjectName("addTitleYearValue")

        self._score_input = QDoubleSpinBox()
        self._score_input.setObjectName("addTitleScoreSpin")
        self._score_input.setRange(USER_SCORE_MIN, USER_SCORE_MAX)
        self._score_input.setSingleStep(USER_SCORE_STEP)
        self._score_input.setDecimals(1)
        self._score_input.setValue(USER_SCORE_MIN)
        self._score_input.valueChanged.connect(self._update_confirm_state)

        score_label = QLabel("Моя оценка")
        score_label.setObjectName("addTitleFieldLabel")
        form.addRow(year_label, self._year_label)
        form.addRow(score_label, self._score_input)
        root_layout.addLayout(form)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self._back_button = QPushButton("Искать другой")
        self._back_button.setObjectName("addTitleSecondaryButton")
        self._back_button.clicked.connect(self._go_search_again)
        if self._transfer_mode:
            self._back_button.hide()
        self._confirm_button = QPushButton(
            "Добавить в watched" if self._transfer_mode else "Добавить тайтл"
        )
        self._confirm_button.setObjectName("addTitleConfirmButton")
        self._confirm_button.clicked.connect(self._confirm_add)
        if self._transfer_mode is False:
            actions.addWidget(self._back_button)
        actions.addStretch()
        actions.addWidget(self._confirm_button)
        root_layout.addLayout(actions)

        preview_entry = ("__preview__", bundle.preview_movie, bundle.preview_card)
        self._detail_card.show_entry(preview_entry)
        self._update_confirm_state()
        self._score_input.setFocus(Qt.FocusReason.OtherFocusReason)

    @property
    def save_result(self):
        return self._save_result

    @staticmethod
    def _format_preview_header(card: dict) -> str:
        title = str(card.get("title") or "").strip() or "Без названия"
        year = card.get("year")
        if year not in (None, ""):
            return f"{title} ({year})"
        return title

    def _format_resolved_year(self, bundle: AddTitleResolveBundle) -> str:
        year = self._resolved_year(bundle)
        if year is None:
            return "не указан"
        return str(year)

    def _resolved_year(self, bundle: AddTitleResolveBundle) -> int | None:
        year = bundle.preview_card.get("year")
        if year in (None, ""):
            year = bundle.defaults.get(scheme.MAIN_INFO, {}).get("year")
        try:
            return int(year)
        except (TypeError, ValueError):
            return None

    def _fill_warning_label(self) -> None:
        if self._transfer_mode and self._bundle.pool_candidate is not None:
            from candidates import service as candidate_service

            if candidate_service.is_pool_candidate_incomplete(self._bundle.pool_candidate):
                self._warning_label.setText(
                    "Кандидат неполный: нет KP/IMDb данных. "
                    "Можно продолжить, но проверьте карточку перед сохранением."
                )
                self._warning_label.show()
                return

        status_lines = format_resolve_status_lines(self._bundle.statuses)
        if self._bundle.found is False:
            self._warning_label.setText(
                "Автоматически данные не найдены. Вернитесь к поиску или укажите только оценку, "
                "если карточка уже содержит корректный год."
            )
            self._warning_label.show()
        elif len(status_lines) > 0:
            self._warning_label.setText(" · ".join(status_lines))
            self._warning_label.show()
        else:
            self._warning_label.hide()

    def _update_confirm_state(self) -> None:
        score_ok = valid.is_correct_score(str(self._score_input.value()))
        year = self._resolved_year(self._bundle)
        year_ok = year is not None and valid.is_correct_year(str(year))
        self._confirm_button.setEnabled(score_ok and year_ok)

    def _go_search_again(self) -> None:
        self.search_again = True
        self.reject()

    def _confirm_add(self) -> None:
        user_score = normalize_user_score_value(self._score_input.value())
        year = self._resolved_year(self._bundle)
        if valid.is_correct_score(str(user_score)) is False:
            QMessageBox.warning(self, "Добавить тайтл", "Укажите корректную оценку (0–10).")
            return
        if year is None or valid.is_correct_year(str(year)) is False:
            QMessageBox.warning(
                self,
                "Добавить тайтл",
                f"Год не задан или некорректен ({YEAR_FILTER_MIN}–{constant.NOW_YEAR}). "
                "Вернитесь к поиску и выберите другой тайтл.",
            )
            return

        self._confirm_button.setEnabled(False)
        result = save_add_title_record(
            self._bundle.defaults,
            user_score,
            meta_payload=self._bundle.meta_payload,
            poster_hints=self._bundle.poster_hints,
            pool_candidate=self._bundle.pool_candidate,
        )
        dialog_title = "Перенос из pool" if self._transfer_mode else "Добавить тайтл"
        if result.ok is False:
            self._confirm_button.setEnabled(True)
            QMessageBox.warning(self, dialog_title, result.message)
            return

        self._save_result = result
        self.accept()


def run_candidate_transfer_flow(parent, candidate: dict):
    """Open preview dialog for pool candidate transfer; returns save result or None."""
    if not isinstance(candidate, dict):
        return None
    bundle = build_candidate_transfer_bundle(candidate)
    preview_dialog = AddTitlePreviewDialog(bundle, parent, transfer_mode=True)
    if preview_dialog.exec() == QDialog.DialogCode.Accepted:
        return preview_dialog.save_result
    return None


def run_add_title_flow(parent=None):
    """Open search dialog, then preview dialog; loop back on «Искать другой»."""
    initial_title = ""
    initial_country = ""

    while True:
        search_dialog = AddTitleSearchDialog(
            parent,
            initial_title=initial_title,
            initial_country=initial_country,
        )
        if search_dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        bundle = search_dialog.resolve_bundle
        if bundle is None:
            return None

        preview_dialog = AddTitlePreviewDialog(bundle, parent)
        if preview_dialog.exec() == QDialog.DialogCode.Accepted:
            return preview_dialog.save_result

        if preview_dialog.search_again is False:
            return None

        initial_title = search_dialog.last_title
        initial_country = search_dialog.last_country


class AddTitleDialog:
    """Backward-compatible entry: runs the two-dialog flow."""

    def __init__(self, parent=None) -> None:
        self._parent = parent
        self._save_result = None

    @property
    def save_result(self):
        return self._save_result

    def exec(self) -> int:
        result = run_add_title_flow(self._parent)
        if result is None:
            return QDialog.DialogCode.Rejected
        self._save_result = result
        return QDialog.DialogCode.Accepted
