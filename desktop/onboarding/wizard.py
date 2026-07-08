"""Startup onboarding wizard for deterministic candidate-pool autofill."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.onboarding.worker import OnboardingAutofillWorker
from desktop.theme.scaling import font_px, scale_px
from desktop.theme.tokens import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_CARD_ALT,
    COLOR_FOCUS_BORDER,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_SOFT,
    FONT_BASE,
    FONT_DIALOG_TITLE,
    FONT_FAMILY_QSS,
    FONT_SMALL,
    FONT_TITLE,
    RADIUS_BUTTON,
    RADIUS_CARD_LARGE,
    SPACING_LARGE,
    SPACING_MEDIUM,
    SPACING_SMALL,
    px,
)


@dataclass(frozen=True)
class _Question:
    key: str
    title_ru: str
    title_en: str
    options: tuple[tuple[str, str, str], ...]


_QUESTIONS: tuple[_Question, ...] = (
    _Question(
        key="media_preference",
        title_ru="Что вы чаще смотрите?",
        title_en="What do you watch more often?",
        options=(
            ("movie", "Фильмы", "Movies"),
            ("tv", "Сериалы", "Series"),
            ("both", "Не важно", "No preference"),
        ),
    ),
    _Question(
        key="release_preference",
        title_ru="Что вам ближе?",
        title_en="Which era feels closer?",
        options=(
            ("classic", "Классика", "Classics"),
            ("new", "Горячие новинки", "New releases"),
            ("mixed", "Не важно", "No preference"),
        ),
    ),
    _Question(
        key="vibe_preference",
        title_ru="Какой вайб чаще хочется?",
        title_en="What vibe do you want more often?",
        options=(
            ("light", "Лёгкий", "Light"),
            ("dark", "Мрачный", "Dark"),
            ("mixed", "Не важно", "No preference"),
        ),
    ),
    _Question(
        key="origin_preference",
        title_ru="Что вам ближе?",
        title_en="Which origin feels closer?",
        options=(
            ("foreign", "Зарубежное", "Foreign"),
            ("domestic", "Отечественное", "Domestic"),
            ("mixed", "Не важно", "No preference"),
        ),
    ),
)


def _wizard_style() -> str:
    return f"""
QDialog#onboardingAutofillDialog {{
    background-color: {COLOR_BG};
    font-family: {FONT_FAMILY_QSS};
}}
QFrame#onboardingCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD_LARGE)}px;
}}
QLabel#onboardingEyebrow {{
    color: {COLOR_ACCENT_HOVER};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 700;
}}
QLabel#onboardingTitle {{
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_TITLE)}px;
    font-weight: 750;
}}
QLabel#onboardingSubtitle, QLabel#onboardingStatus {{
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
}}
QLabel#onboardingDot {{
    color: {COLOR_TEXT_MUTED};
    font-size: {font_px(FONT_SMALL)}px;
}}
QLabel#onboardingDot[active="true"] {{
    color: {COLOR_ACCENT};
}}
QPushButton#onboardingOption {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_DIALOG_TITLE)}px;
    font-weight: 650;
    padding: {px(15)}px {px(18)}px;
    text-align: left;
}}
QPushButton#onboardingOption:hover {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_FOCUS_BORDER};
}}
QPushButton#onboardingOption:checked {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_ACCENT};
    color: {COLOR_TEXT};
}}
QPushButton#onboardingNext, QPushButton#onboardingOpen {{
    background-color: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 700;
    padding: {px(10)}px {px(20)}px;
    min-width: {px(120)}px;
}}
QPushButton#onboardingNext:hover, QPushButton#onboardingOpen:hover {{
    background-color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
QPushButton#onboardingNext:disabled {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_BORDER};
    color: {COLOR_TEXT_MUTED};
}}
QPushButton#onboardingBack, QPushButton#onboardingSkip {{
    background-color: transparent;
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 650;
    padding: {px(10)}px {px(18)}px;
}}
QPushButton#onboardingBack:hover, QPushButton#onboardingSkip:hover {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_FOCUS_BORDER};
    color: {COLOR_TEXT};
}}
QProgressBar#onboardingProgress {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_SMALL)}px;
    text-align: center;
    min-height: {px(20)}px;
}}
QProgressBar#onboardingProgress::chunk {{
    background-color: {COLOR_ACCENT};
    border-radius: {px(RADIUS_BUTTON)}px;
}}
QLabel#onboardingWarning {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_SMALL)}px;
    padding: {px(10)}px {px(12)}px;
}}
"""


class OnboardingAutofillDialog(QDialog):
    """Large-card wizard that collects taste and starts deterministic autofill."""

    completed = pyqtSignal(object)

    def __init__(self, *, ui_language: str = "ru", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("onboardingAutofillDialog")
        self.setModal(True)
        self.resize(scale_px(760), scale_px(560))
        self.setMinimumSize(scale_px(620), scale_px(480))
        self.setStyleSheet(_wizard_style())
        self._ui_language = "en" if str(ui_language or "").casefold().startswith("en") else "ru"
        self._answers: dict[str, str] = {}
        self._question_pages: list[tuple[_Question, QWidget, QButtonGroup]] = []
        self._worker: OnboardingAutofillWorker | None = None
        self._fade_animation: QPropertyAnimation | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(scale_px(22), scale_px(22), scale_px(22), scale_px(22))
        root_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("onboardingCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root_layout.addWidget(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            scale_px(34),
            scale_px(30),
            scale_px(34),
            scale_px(28),
        )
        card_layout.setSpacing(scale_px(SPACING_LARGE))

        self._dots = QWidget()
        self._dots_layout = QHBoxLayout(self._dots)
        self._dots_layout.setContentsMargins(0, 0, 0, 0)
        self._dots_layout.setSpacing(scale_px(7))
        card_layout.addWidget(self._dots)

        self._stack = QStackedWidget()
        self._stack.setObjectName("onboardingStack")
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout.addWidget(self._stack, 1)

        for question in self._active_questions():
            self._add_question_page(question)
        self._loading_page = self._build_loading_page()
        self._stack.addWidget(self._loading_page)
        self._rebuild_dots()

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(scale_px(SPACING_MEDIUM))
        self._back_button = QPushButton("Назад" if self._ui_language == "ru" else "Back")
        self._back_button.setObjectName("onboardingBack")
        self._back_button.clicked.connect(self._go_back)
        controls.addWidget(self._back_button)
        controls.addStretch(1)
        self._next_button = QPushButton("Далее" if self._ui_language == "ru" else "Next")
        self._next_button.setObjectName("onboardingNext")
        self._next_button.clicked.connect(self._go_next)
        controls.addWidget(self._next_button)
        card_layout.addLayout(controls)

        self._sync_controls()

    def _active_questions(self) -> list[_Question]:
        questions = list(_QUESTIONS[:3])
        if self._ui_language == "ru":
            questions.append(_QUESTIONS[3])
        return questions

    def _text(self, ru: str, en: str) -> str:
        return en if self._ui_language == "en" else ru

    def _add_question_page(self, question: _Question) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scale_px(SPACING_LARGE))

        eyebrow = QLabel(self._text("Стартовая настройка", "Starter setup"))
        eyebrow.setObjectName("onboardingEyebrow")
        layout.addWidget(eyebrow)

        title = QLabel(self._text(question.title_ru, question.title_en))
        title.setObjectName("onboardingTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        subtitle = QLabel(self._text("Выберите один вариант, чтобы собрать первый пул.", "Choose one option to build the first pool."))
        subtitle.setObjectName("onboardingSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        group = QButtonGroup(self)
        group.setExclusive(True)
        group.buttonClicked.connect(lambda _button, key=question.key: self._on_option_selected(key))

        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(0, scale_px(SPACING_SMALL), 0, 0)
        options_layout.setSpacing(scale_px(SPACING_MEDIUM))
        for value, label_ru, label_en in question.options:
            button = QPushButton(self._text(label_ru, label_en))
            button.setObjectName("onboardingOption")
            button.setCheckable(True)
            button.setProperty("answer", value)
            button.setMinimumHeight(scale_px(58))
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            group.addButton(button)
            options_layout.addWidget(button)
        layout.addLayout(options_layout)
        layout.addStretch(1)

        self._stack.addWidget(page)
        self._question_pages.append((question, page, group))

    def _build_loading_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scale_px(SPACING_LARGE))

        eyebrow = QLabel(self._text("Пул кандидатов", "Candidate pool"))
        eyebrow.setObjectName("onboardingEyebrow")
        layout.addWidget(eyebrow)

        title = QLabel(self._text("Собираем первый пул", "Building the first pool"))
        title.setObjectName("onboardingTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        self._status_label = QLabel(self._text("Подготовка...", "Preparing..."))
        self._status_label.setObjectName("onboardingStatus")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setObjectName("onboardingProgress")
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._warning_label = QLabel("")
        self._warning_label.setObjectName("onboardingWarning")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        layout.addWidget(self._warning_label)

        layout.addStretch(1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addStretch(1)
        self._skip_button = QPushButton(self._text("Пропустить", "Skip"))
        self._skip_button.setObjectName("onboardingSkip")
        self._skip_button.clicked.connect(self._skip)
        actions.addWidget(self._skip_button)
        self._open_button = QPushButton(self._text("Открыть кандидаты", "Open Candidates"))
        self._open_button.setObjectName("onboardingOpen")
        self._open_button.setVisible(False)
        self._open_button.clicked.connect(self._finish)
        actions.addWidget(self._open_button)
        layout.addLayout(actions)
        return page

    def _rebuild_dots(self) -> None:
        while self._dots_layout.count():
            item = self._dots_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index in range(len(self._question_pages) + 1):
            dot = QLabel("●")
            dot.setObjectName("onboardingDot")
            dot.setProperty("active", "true" if index == self._stack.currentIndex() else "false")
            dot.style().unpolish(dot)
            dot.style().polish(dot)
            self._dots_layout.addWidget(dot)
        self._dots_layout.addStretch(1)

    def _set_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._animate_current_page()
        self._rebuild_dots()
        self._sync_controls()

    def _animate_current_page(self) -> None:
        widget = self._stack.currentWidget()
        if widget is None:
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        self._fade_animation = animation
        animation.start()

    def _selected_answer(self, group: QButtonGroup) -> str | None:
        button = group.checkedButton()
        if button is None:
            return None
        return str(button.property("answer") or "").strip() or None

    def _current_question(self) -> tuple[_Question, QButtonGroup] | None:
        index = self._stack.currentIndex()
        if index < 0 or index >= len(self._question_pages):
            return None
        question, _page, group = self._question_pages[index]
        return question, group

    def _on_option_selected(self, key: str) -> None:
        current = self._current_question()
        if current is None:
            return
        question, group = current
        if question.key != key:
            return
        selected = self._selected_answer(group)
        if selected is not None:
            self._answers[key] = selected
        self._sync_controls()

    def _sync_controls(self) -> None:
        index = self._stack.currentIndex()
        loading = index >= len(self._question_pages)
        self._back_button.setVisible(not loading)
        self._next_button.setVisible(not loading)
        self._back_button.setEnabled(index > 0 and not loading)
        current = self._current_question()
        self._next_button.setEnabled(current is not None and self._selected_answer(current[1]) is not None)
        if current is not None and index == len(self._question_pages) - 1:
            self._next_button.setText(self._text("Собрать пул", "Build pool"))
        else:
            self._next_button.setText(self._text("Далее", "Next"))

    def _go_back(self) -> None:
        index = self._stack.currentIndex()
        if index > 0:
            self._set_page(index - 1)

    def _go_next(self) -> None:
        current = self._current_question()
        if current is None:
            return
        question, group = current
        selected = self._selected_answer(group)
        if selected is None:
            return
        self._answers[question.key] = selected
        next_index = self._stack.currentIndex() + 1
        if next_index < len(self._question_pages):
            self._set_page(next_index)
            return
        self._start_autofill()

    def _profile(self) -> dict[str, Any]:
        return {
            "ui_language": self._ui_language,
            "media_preference": self._answers.get("media_preference") or "both",
            "release_preference": self._answers.get("release_preference") or "mixed",
            "vibe_preference": self._answers.get("vibe_preference") or "mixed",
            "origin_preference": self._answers.get("origin_preference") if self._ui_language == "ru" else None,
        }

    def _start_autofill(self) -> None:
        self._set_page(len(self._question_pages))
        self._progress.setRange(0, 100)
        self._progress.setValue(5)
        self._status_label.setText(self._text("Настраиваем вкус", "Configuring taste"))
        self._skip_button.setVisible(True)
        self._open_button.setVisible(False)
        self._worker = OnboardingAutofillWorker(self._profile(), self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_with_result.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        message = str(data.get("message") or "")
        if message:
            self._status_label.setText(message)
        stage = int(data.get("stage") or 1)
        completed = data.get("completed_buckets")
        total = data.get("total_buckets")
        if isinstance(completed, int) and isinstance(total, int) and total > 0:
            value = min(95, max(5, int((completed / total) * 90)))
        else:
            value = min(95, max(5, stage * 15))
        self._progress.setValue(value)

    def _on_finished(self, result: object) -> None:
        data = result if isinstance(result, dict) else {}
        self._progress.setValue(100)
        created = int(data.get("created_count") or 0)
        cancelled = bool(data.get("cancelled"))
        if cancelled:
            self._status_label.setText(self._text(f"Остановлено. Сохранено кандидатов: {created}", f"Stopped. Saved candidates: {created}"))
        else:
            self._status_label.setText(self._text(f"Готово. Кандидатов: {created}", f"Done. Candidates: {created}"))
        warning = data.get("warning")
        if warning:
            self._warning_label.setText(str(warning))
            self._warning_label.setVisible(True)
        self._skip_button.setVisible(False)
        self._open_button.setVisible(True)
        self._open_button.setFocus()
        if not warning:
            QTimer.singleShot(700, self._finish)

    def _on_failed(self, message: str) -> None:
        self._progress.setValue(0)
        self._status_label.setText(self._text("Не удалось собрать пул.", "Could not build the pool."))
        self._warning_label.setText(str(message))
        self._warning_label.setVisible(True)
        self._skip_button.setVisible(False)
        self._open_button.setVisible(True)

    def _skip(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._skip_button.setEnabled(False)
            self._status_label.setText(self._text("Останавливаем...", "Stopping..."))
            return
        self.reject()

    def _finish(self) -> None:
        self.completed.emit({"profile": self._profile()})
        self.accept()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
