"""Add-title preview dialog: card review and confirm save."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from common import valid
from config import constant
from config import scheme
from dataset import service
from diagnostics.gui_event_log import log_event
from desktop.shared.detail import ADD_TITLE_PREVIEW_CARD_PROFILE, WatchedDetailCard
from desktop.watched.add_title.constants import (
    ADD_TITLE_DIALOG_STYLE,
    PREVIEW_CARD_SCROLL_MIN_HEIGHT,
    PREVIEW_DIALOG_HEIGHT,
    PREVIEW_DIALOG_WIDTH,
)
from desktop.watched.model import (
    USER_SCORE_MAX,
    USER_SCORE_MIN,
    USER_SCORE_STEP,
    YEAR_FILTER_MIN,
    normalize_user_score_value,
)


class AddTitlePreviewDialog(QDialog):
    """Preview card and confirm. Closes on save or «Искать другой»."""

    def __init__(
        self,
        bundle: service.AddTitleResolveBundle,
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

    def _format_resolved_year(self, bundle: service.AddTitleResolveBundle) -> str:
        year = self._resolved_year(bundle)
        if year is None:
            return "не указан"
        return str(year)

    def _resolved_year(self, bundle: service.AddTitleResolveBundle) -> int | None:
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

        status_lines = service.format_resolve_status_lines(self._bundle.statuses)
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
        log_event("add_title.preview.search_again")
        self.search_again = True
        self.reject()

    def _confirm_add(self) -> None:
        user_score = normalize_user_score_value(self._score_input.value())
        year = self._resolved_year(self._bundle)
        log_event(
            "add_title.preview.confirm_clicked",
            **{
                "title": self._bundle.preview_card.get("title"),
                "resolved_year": year,
                "score": user_score,
                "transfer_mode": self._transfer_mode,
            },
        )
        if valid.is_correct_score(str(user_score)) is False:
            log_event("add_title.preview.invalid_score", score=user_score)
            QMessageBox.warning(self, "Добавить тайтл", "Укажите корректную оценку (0–10).")
            return
        if year is None or valid.is_correct_year(str(year)) is False:
            log_event("add_title.preview.invalid_year", **{"resolved_year": year})
            QMessageBox.warning(
                self,
                "Добавить тайтл",
                f"Год не задан или некорректен ({YEAR_FILTER_MIN}–{constant.NOW_YEAR}). "
                "Вернитесь к поиску и выберите другой тайтл.",
            )
            return

        self._confirm_button.setEnabled(False)
        result = service.save_add_title_record(
            self._bundle.defaults,
            user_score,
            meta_payload=self._bundle.meta_payload,
            poster_hints=self._bundle.poster_hints,
            pool_candidate=self._bundle.pool_candidate,
        )
        dialog_title = "Перенос из pool" if self._transfer_mode else "Добавить тайтл"
        if result.ok is False:
            self._confirm_button.setEnabled(True)
            log_event("add_title.preview.save_failed", message=result.message)
            QMessageBox.warning(self, dialog_title, result.message)
            return

        self._save_result = result
        log_event("add_title.preview.save_ok", message=result.message)
        self.accept()
