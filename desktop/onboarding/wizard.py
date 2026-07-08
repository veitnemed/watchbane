"""Startup onboarding wizard for deterministic candidate-pool autofill."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication
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

from candidates import service as candidate_service
from desktop.settings.app_settings import AppSettings, get_persisted_data_language, normalize_ui_scale, save_app_settings
from desktop.onboarding.worker import OnboardingAutofillWorker
from desktop.theme.scaling import font_px, get_ui_scale, scale_px
from desktop.theme.scaling import set_ui_scale
from desktop.theme.ui_modules import ensure_scaled_ui_modules
from desktop.theme.tokens import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_BORDER_HOVER,
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

ONBOARDING_BASE_WIDTH = 960
ONBOARDING_BASE_HEIGHT = 640
ONBOARDING_MIN_WIDTH = 720
ONBOARDING_MIN_HEIGHT = 520
ONBOARDING_SCALE_PRESETS: tuple[tuple[float, str], ...] = (
    (0.90, "90%"),
    (1.00, "100%"),
    (1.15, "115%"),
    (1.30, "130%"),
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
QWidget#onboardingDots,
QStackedWidget#onboardingStack,
QWidget#onboardingPage {{
    background-color: transparent;
    border: 0;
}}
QLabel#onboardingEyebrow {{
    background-color: transparent;
    border: 0;
    color: {COLOR_ACCENT_HOVER};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 700;
}}
QLabel#onboardingTitle {{
    background-color: transparent;
    border: 0;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_TITLE)}px;
    font-weight: 750;
}}
QLabel#onboardingSubtitle, QLabel#onboardingStatus {{
    background-color: transparent;
    border: 0;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
}}
QLabel#onboardingDot {{
    background-color: transparent;
    border: 0;
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
    border-color: {COLOR_BORDER_HOVER};
}}
QPushButton#onboardingOption:focus {{
    border-color: {COLOR_BORDER};
}}
QPushButton#onboardingOption:checked {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_ACCENT};
    color: {COLOR_TEXT};
}}
QPushButton#onboardingOption:checked:focus {{
    border-color: {COLOR_ACCENT};
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
QLabel#onboardingPlanSummary,
QLabel#onboardingScalePreview,
QLabel#onboardingFinalSummary {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(12)}px {px(14)}px;
}}
"""


class OnboardingAutofillDialog(QDialog):
    """Large-card wizard that collects taste and starts deterministic autofill."""

    completed = pyqtSignal(object)

    def __init__(self, *, ui_language: str = "ru", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("onboardingAutofillDialog")
        self.setModal(True)
        self.setMinimumSize(scale_px(ONBOARDING_MIN_WIDTH), scale_px(ONBOARDING_MIN_HEIGHT))
        self._resize_for_launch()
        self.setStyleSheet(_wizard_style())
        self._ui_language = "en" if str(ui_language or "").casefold().startswith("en") else "ru"
        self._ui_scale = normalize_ui_scale(get_ui_scale())
        self._answers: dict[str, str] = {}
        self._question_pages: list[tuple[_Question, QWidget, QButtonGroup]] = []
        self._worker: OnboardingAutofillWorker | None = None
        self._fade_animation: QPropertyAnimation | None = None
        self._last_result: dict[str, Any] = {}

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
        self._dots.setObjectName("onboardingDots")
        self._dots_layout = QHBoxLayout(self._dots)
        self._dots_layout.setContentsMargins(0, 0, 0, 0)
        self._dots_layout.setSpacing(scale_px(7))
        card_layout.addWidget(self._dots)

        self._stack = QStackedWidget()
        self._stack.setObjectName("onboardingStack")
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout.addWidget(self._stack, 1)

        self._setup_page = self._build_setup_page()
        self._stack.addWidget(self._setup_page)
        for question in self._active_questions():
            self._add_question_page(question)
        self._plan_page = self._build_plan_page()
        self._stack.addWidget(self._plan_page)
        self._loading_page = self._build_loading_page()
        self._stack.addWidget(self._loading_page)
        self._final_page = self._build_final_page()
        self._stack.addWidget(self._final_page)
        self._rebuild_dots()

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(scale_px(SPACING_MEDIUM))
        self._back_button = QPushButton("Назад" if self._ui_language == "ru" else "Back")
        self._back_button.setObjectName("onboardingBack")
        self._back_button.clicked.connect(self._go_back)
        controls.addWidget(self._back_button)
        self._footer_skip_button = QPushButton("Пропустить" if self._ui_language == "ru" else "Skip")
        self._footer_skip_button.setObjectName("onboardingSkip")
        self._footer_skip_button.clicked.connect(self._skip)
        controls.addWidget(self._footer_skip_button)
        controls.addStretch(1)
        self._next_button = QPushButton("Далее" if self._ui_language == "ru" else "Next")
        self._next_button.setObjectName("onboardingNext")
        self._next_button.clicked.connect(self._go_next)
        controls.addWidget(self._next_button)
        card_layout.addLayout(controls)

        self._sync_controls()

    def _resize_for_launch(self) -> None:
        parent = self.parentWidget()
        if parent is not None and parent.width() > 0 and parent.height() > 0:
            self.resize(
                max(scale_px(ONBOARDING_MIN_WIDTH), parent.width()),
                max(scale_px(ONBOARDING_MIN_HEIGHT), parent.height()),
            )
            return
        self.resize(scale_px(ONBOARDING_BASE_WIDTH), scale_px(ONBOARDING_BASE_HEIGHT))

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._resize_for_launch()
        super().showEvent(event)

    def _active_questions(self) -> list[_Question]:
        questions = list(_QUESTIONS[:3])
        if self._ui_language == "ru":
            questions.append(_QUESTIONS[3])
        return questions

    def _text(self, ru: str, en: str) -> str:
        return en if self._ui_language == "en" else ru

    def _question_start_index(self) -> int:
        return 1

    def _plan_index(self) -> int:
        return self._question_start_index() + len(self._question_pages)

    def _loading_index(self) -> int:
        return self._plan_index() + 1

    def _final_index(self) -> int:
        return self._loading_index() + 1

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("onboardingPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scale_px(SPACING_LARGE))

        self._setup_eyebrow = QLabel(self._text("Первый запуск", "First launch"))
        self._setup_eyebrow.setObjectName("onboardingEyebrow")
        layout.addWidget(self._setup_eyebrow)

        self._setup_title = QLabel(self._text("Настройте интерфейс", "Set up the interface"))
        self._setup_title.setObjectName("onboardingTitle")
        self._setup_title.setWordWrap(True)
        layout.addWidget(self._setup_title)

        self._setup_subtitle = QLabel(self._text(
            "Выберите язык и комфортный масштаб. Изменения применяются сразу.",
            "Choose language and comfortable UI scale. Changes apply immediately.",
        ))
        self._setup_subtitle.setObjectName("onboardingSubtitle")
        self._setup_subtitle.setWordWrap(True)
        layout.addWidget(self._setup_subtitle)

        language_row = QHBoxLayout()
        language_row.setContentsMargins(0, scale_px(SPACING_SMALL), 0, 0)
        language_row.setSpacing(scale_px(SPACING_MEDIUM))
        self._language_group = QButtonGroup(self)
        self._language_group.setExclusive(True)
        for value, label in (("ru", "Русский"), ("en", "English")):
            button = QPushButton(label)
            button.setObjectName("onboardingOption")
            button.setCheckable(True)
            button.setProperty("answer", value)
            button.setMinimumHeight(scale_px(54))
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setChecked(value == self._ui_language)
            self._language_group.addButton(button)
            language_row.addWidget(button)
        self._language_group.buttonClicked.connect(self._on_language_selected)
        layout.addLayout(language_row)

        scale_row = QHBoxLayout()
        scale_row.setContentsMargins(0, 0, 0, 0)
        scale_row.setSpacing(scale_px(SPACING_MEDIUM))
        self._scale_group = QButtonGroup(self)
        self._scale_group.setExclusive(True)
        for value, label in ONBOARDING_SCALE_PRESETS:
            button = QPushButton(label)
            button.setObjectName("onboardingOption")
            button.setCheckable(True)
            button.setProperty("answer", value)
            button.setMinimumHeight(scale_px(54))
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setChecked(abs(value - self._ui_scale) < 0.01)
            self._scale_group.addButton(button)
            scale_row.addWidget(button)
        self._scale_group.buttonClicked.connect(self._on_scale_selected)
        layout.addLayout(scale_row)

        self._scale_preview = QLabel("")
        self._scale_preview.setObjectName("onboardingScalePreview")
        self._scale_preview.setWordWrap(True)
        layout.addWidget(self._scale_preview)
        layout.addStretch(1)
        self._update_setup_text()
        return page

    def _update_setup_text(self) -> None:
        if hasattr(self, "_setup_eyebrow"):
            self._setup_eyebrow.setText(self._text("Первый запуск", "First launch"))
            self._setup_title.setText(self._text("Настройте интерфейс", "Set up the interface"))
            self._setup_subtitle.setText(self._text(
                "Выберите язык и комфортный масштаб. Изменения применяются сразу.",
                "Choose language and comfortable UI scale. Changes apply immediately.",
            ))
            if hasattr(self, "_back_button"):
                self._back_button.setText(self._text("Назад", "Back"))
                self._footer_skip_button.setText(self._text("Пропустить", "Skip"))
                self._next_button.setText(self._text("Далее", "Next"))
        if hasattr(self, "_scale_preview"):
            percent = int(round(float(self._ui_scale) * 100))
            self._scale_preview.setText(self._text(
                f"Предпросмотр: карточки, кнопки и текст будут открываться примерно на {percent}%.",
                f"Preview: cards, buttons and text will open at about {percent}%.",
            ))

    def _on_language_selected(self, button: QPushButton) -> None:
        value = str(button.property("answer") or "").strip().casefold()
        if value not in {"ru", "en"} or value == self._ui_language:
            return
        self._ui_language = value
        if self._ui_language != "ru":
            self._answers.pop("origin_preference", None)
        save_app_settings(AppSettings(
            ui_scale=self._ui_scale,
            interface_language=self._ui_language,
            data_language=get_persisted_data_language(),
        ))
        self._update_setup_text()
        self._rebuild_question_and_result_pages()

    def _on_scale_selected(self, button: QPushButton) -> None:
        value = normalize_ui_scale(button.property("answer"))
        self._ui_scale = value
        set_ui_scale(value)
        ensure_scaled_ui_modules()
        save_app_settings(AppSettings(
            ui_scale=value,
            interface_language=self._ui_language,
            data_language=get_persisted_data_language(),
        ))
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(app.styleSheet())
        self._update_setup_text()

    def _rebuild_question_and_result_pages(self) -> None:
        current = self._stack.currentIndex()
        while self._stack.count() > 1:
            widget = self._stack.widget(1)
            self._stack.removeWidget(widget)
            widget.deleteLater()
        self._question_pages.clear()
        for question in self._active_questions():
            self._add_question_page(question)
        self._plan_page = self._build_plan_page()
        self._stack.addWidget(self._plan_page)
        self._loading_page = self._build_loading_page()
        self._stack.addWidget(self._loading_page)
        self._final_page = self._build_final_page()
        self._stack.addWidget(self._final_page)
        self._set_page(min(current, self._plan_index()))

    def _add_question_page(self, question: _Question) -> None:
        page = QWidget()
        page.setObjectName("onboardingPage")
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

    def _build_plan_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("onboardingPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scale_px(SPACING_LARGE))

        eyebrow = QLabel(self._text("План автозаполнения", "Autofill plan"))
        eyebrow.setObjectName("onboardingEyebrow")
        layout.addWidget(eyebrow)

        title = QLabel(self._text("Проверим первый пул до API-запросов", "Review the first pool before API calls"))
        title.setObjectName("onboardingTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        subtitle = QLabel(self._text(
            "Watchbane соберёт кандидатов по выбранным пропорциям. Никаких запросов к TMDb ещё не было.",
            "Watchbane will build candidates using these proportions. No TMDb requests have been made yet.",
        ))
        subtitle.setObjectName("onboardingSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._plan_summary_label = QLabel("")
        self._plan_summary_label.setObjectName("onboardingPlanSummary")
        self._plan_summary_label.setWordWrap(True)
        layout.addWidget(self._plan_summary_label)
        layout.addStretch(1)
        return page

    def _build_loading_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("onboardingPage")
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

    def _build_final_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("onboardingPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scale_px(SPACING_LARGE))

        eyebrow = QLabel(self._text("Готово", "Done"))
        eyebrow.setObjectName("onboardingEyebrow")
        layout.addWidget(eyebrow)

        self._final_title = QLabel(self._text("Пул кандидатов готов", "Candidate pool is ready"))
        self._final_title.setObjectName("onboardingTitle")
        self._final_title.setWordWrap(True)
        layout.addWidget(self._final_title)

        self._final_summary = QLabel("")
        self._final_summary.setObjectName("onboardingFinalSummary")
        self._final_summary.setWordWrap(True)
        layout.addWidget(self._final_summary)
        layout.addStretch(1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addStretch(1)
        self._retry_button = QPushButton(self._text("Повторить сборку", "Retry build"))
        self._retry_button.setObjectName("onboardingSkip")
        self._retry_button.clicked.connect(self._start_autofill)
        self._retry_button.setVisible(False)
        actions.addWidget(self._retry_button)
        self._final_open_button = QPushButton(self._text("Открыть кандидаты", "Open Candidates"))
        self._final_open_button.setObjectName("onboardingOpen")
        self._final_open_button.clicked.connect(self._finish)
        actions.addWidget(self._final_open_button)
        layout.addLayout(actions)
        return page

    def _format_plan_summary(self) -> str:
        plan = candidate_service.get_onboarding_autofill_plan_view(self._profile())
        quotas = plan.get("quotas") or {}
        media = quotas.get("media_type") or {}
        release = quotas.get("release") or {}
        vibe = quotas.get("vibe") or {}
        origin = quotas.get("origin") or {}
        lines = [
            self._text(f"Цель: {plan.get('target')} кандидатов", f"Target: {plan.get('target')} candidates"),
            self._text(f"Фильмы: {media.get('movie', 0)}, сериалы: {media.get('tv', 0)}", f"Movies: {media.get('movie', 0)}, series: {media.get('tv', 0)}"),
            self._text(
                f"Классика: {release.get('classic_sweep', 0)}, новинки: {release.get('new_sweep', 0)}, топ: {release.get('top_all_time', 0)}",
                f"Classics: {release.get('classic_sweep', 0)}, new: {release.get('new_sweep', 0)}, top: {release.get('top_all_time', 0)}",
            ),
            self._text(f"Лёгкий вайб: {vibe.get('light', 0)}, мрачный: {vibe.get('dark', 0)}", f"Light vibe: {vibe.get('light', 0)}, dark: {vibe.get('dark', 0)}"),
        ]
        if self._ui_language == "ru":
            lines.append(f"Отечественное: {origin.get('domestic', 0)}, зарубежное: {origin.get('foreign', 0)}")
        lines.append(self._text(f"Срезов поиска: {plan.get('bucket_count')}", f"Search slices: {plan.get('bucket_count')}"))
        return "\n".join(lines)

    def _update_plan_summary(self) -> None:
        if hasattr(self, "_plan_summary_label"):
            self._plan_summary_label.setText(self._format_plan_summary())

    def _rebuild_dots(self) -> None:
        while self._dots_layout.count():
            item = self._dots_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index in range(self._stack.count()):
            dot = QLabel("●")
            dot.setObjectName("onboardingDot")
            dot.setProperty("active", "true" if index == self._stack.currentIndex() else "false")
            dot.style().unpolish(dot)
            dot.style().polish(dot)
            self._dots_layout.addWidget(dot)
        self._dots_layout.addStretch(1)

    def _set_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        if index == self._plan_index():
            self._update_plan_summary()
        self._animate_current_page()
        self._rebuild_dots()
        self._sync_controls()

    def _animate_current_page(self) -> None:
        widget = self._stack.currentWidget()
        if widget is None:
            return
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            widget.setGraphicsEffect(None)
            return
        if self._fade_animation is not None:
            self._fade_animation.stop()
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
        index = self._stack.currentIndex() - self._question_start_index()
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
        loading_or_final = index >= self._loading_index()
        self._back_button.setVisible(not loading_or_final)
        self._footer_skip_button.setVisible(not loading_or_final)
        self._next_button.setVisible(not loading_or_final)
        self._back_button.setEnabled(index > 0 and not loading_or_final)
        current = self._current_question()
        on_setup = index == 0
        on_plan = index == self._plan_index()
        self._next_button.setEnabled(
            on_setup
            or on_plan
            or (current is not None and self._selected_answer(current[1]) is not None)
        )
        if on_plan:
            self._next_button.setText(self._text("Собрать пул", "Build pool"))
        else:
            self._next_button.setText(self._text("Далее", "Next"))

    def _go_back(self) -> None:
        index = self._stack.currentIndex()
        if index > 0:
            self._set_page(index - 1)

    def _go_next(self) -> None:
        index = self._stack.currentIndex()
        if index == 0:
            self._set_page(1)
            return
        if index == self._plan_index():
            self._start_autofill()
            return
        current = self._current_question()
        if current is None:
            return
        question, group = current
        selected = self._selected_answer(group)
        if selected is None:
            return
        self._answers[question.key] = selected
        next_index = self._stack.currentIndex() + 1
        self._set_page(next_index)

    def _profile(self) -> dict[str, Any]:
        return {
            "ui_language": self._ui_language,
            "media_preference": self._answers.get("media_preference") or "both",
            "release_preference": self._answers.get("release_preference") or "mixed",
            "vibe_preference": self._answers.get("vibe_preference") or "mixed",
            "origin_preference": self._answers.get("origin_preference") if self._ui_language == "ru" else None,
        }

    def _start_autofill(self) -> None:
        self._set_page(self._loading_index())
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
        self._last_result = dict(data)
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
        self._show_final_result(data, failed=False)

    def _on_failed(self, message: str) -> None:
        self._last_result = {"created_count": 0, "warning": str(message), "ok": False}
        self._progress.setValue(0)
        self._status_label.setText(self._text("Не удалось собрать пул.", "Could not build the pool."))
        self._warning_label.setText(str(message))
        self._warning_label.setVisible(True)
        self._skip_button.setVisible(False)
        self._open_button.setVisible(True)
        self._show_final_result(self._last_result, failed=True)

    def _show_final_result(self, data: dict[str, Any], *, failed: bool) -> None:
        created = int(data.get("created_count") or 0)
        warning = str(data.get("warning") or "").strip()
        if failed or created == 0:
            self._final_title.setText(self._text("Пул не собран", "Pool was not built"))
            self._retry_button.setVisible(True)
            summary = self._text(
                "Кандидаты не добавлены. Можно открыть приложение без стартового пула или повторить сборку.",
                "No candidates were added. You can open the app without a starter pool or retry.",
            )
        else:
            self._final_title.setText(self._text("Пул кандидатов готов", "Candidate pool is ready"))
            self._retry_button.setVisible(False)
            summary = self._text(
                f"Добавлено кандидатов: {created}. Следующий шаг — открыть вкладку кандидатов.",
                f"Candidates added: {created}. Next step: open the Candidates tab.",
            )
        if warning:
            summary = f"{summary}\n{warning}"
        self._final_summary.setText(summary)
        self._set_page(self._final_index())

    def _skip(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._skip_button.setEnabled(False)
            self._status_label.setText(self._text("Останавливаем...", "Stopping..."))
            return
        self.reject()

    def _finish(self) -> None:
        self.completed.emit({"profile": self._profile(), "result": dict(self._last_result)})
        self.accept()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
