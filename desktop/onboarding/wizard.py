"""Startup onboarding wizard for deterministic candidate-pool autofill."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from candidates import service as candidate_service
from candidates.models import country_reference
from candidates.onboarding.taste_presets import (
    ANIMATION_MODE_ANIMATION_ONLY,
    ANIMATION_MODE_ANY,
    ANIMATION_MODE_LIVE_ACTION_ONLY,
    PRESET_ANIME,
    PRESET_BRITISH_EUROPEAN_DETECTIVE,
    PRESET_DARK_THRILLER_CRIME,
    PRESET_FAMILY_ANIMATION,
    PRESET_HOLLYWOOD_MAINSTREAM,
    PRESET_K_DRAMA,
    PRESET_MANUAL,
    PRESET_RUSSIAN_MAINSTREAM,
    PRESET_TURKISH_DRAMAS,
    get_taste_preset,
)
from desktop.settings.app_settings import AppSettings, get_persisted_data_language, normalize_ui_scale, save_app_settings
from desktop.onboarding.worker import OnboardingAutofillWorker
from desktop.shared.brand_assets import watchbane_wordmark_label
from desktop.shared.widgets.genre_chip_selector import FlowLayout
from desktop.theme.scaling import font_px, get_ui_scale, scale_px
from desktop.theme.scaling import set_ui_scale
from desktop.theme.ui_modules import ensure_scaled_ui_modules
from desktop.theme.tokens import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_SOFT,
    COLOR_BORDER,
    COLOR_BORDER_HOVER,
    COLOR_CARD_ALT,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_SOFT,
    FONT_BASE,
    FONT_DIALOG_TITLE,
    FONT_FAMILY,
    FONT_FAMILY_QSS,
    FONT_SMALL,
    RADIUS_BUTTON,
    SPACING_LARGE,
    SPACING_MEDIUM,
    SPACING_SMALL,
    px,
)

ONBOARDING_BASE_WIDTH = 1586
ONBOARDING_BASE_HEIGHT = 992
ONBOARDING_MIN_WIDTH = 720
ONBOARDING_MIN_HEIGHT = 520
ONBOARDING_SCALE_PRESETS: tuple[tuple[float, str], ...] = (
    (0.90, "90%"),
    (1.00, "100%"),
    (1.15, "115%"),
    (1.30, "130%"),
)
ONBOARDING_COUNTRY_CODES: tuple[str, ...] = ("US", "RU", "GB", "KR", "JP")
ONBOARDING_COUNTRY_DEFAULT: tuple[str, ...] = ("US",)
ONBOARDING_COUNTRY_PICKER_LIMIT = 5


@dataclass(frozen=True)
class _PresetCard:
    key: str
    title_ru: str
    title_en: str
    description_ru: str
    description_en: str


_PRESET_CARDS: tuple[_PresetCard, ...] = (
    _PresetCard(
        PRESET_MANUAL,
        "Вручную",
        "Manual",
        "Выберите страны сами.",
        "Choose countries yourself.",
    ),
    _PresetCard(
        PRESET_HOLLYWOOD_MAINSTREAM,
        "Голливуд",
        "Hollywood",
        "США, фильмы и сериалы.",
        "US movies and series.",
    ),
    _PresetCard(
        PRESET_RUSSIAN_MAINSTREAM,
        "Российское",
        "Russian",
        "Фильмы и сериалы РФ.",
        "Russian movies and series.",
    ),
    _PresetCard(
        PRESET_ANIME,
        "Аниме",
        "Anime",
        "Япония, анимация.",
        "Japan animation.",
    ),
    _PresetCard(
        PRESET_K_DRAMA,
        "K-драмы",
        "K-dramas",
        "Корея, сериалы, без анимации.",
        "Korean live-action series.",
    ),
    _PresetCard(
        PRESET_TURKISH_DRAMAS,
        "Турецкие драмы",
        "Turkish dramas",
        "Турция, сериалы.",
        "Turkey live-action series.",
    ),
    _PresetCard(
        PRESET_BRITISH_EUROPEAN_DETECTIVE,
        "Европейский детектив",
        "European detective",
        "Детективы Европы.",
        "European detective series.",
    ),
    _PresetCard(
        PRESET_FAMILY_ANIMATION,
        "Семейная анимация",
        "Family animation",
        "Семейный animation-пул.",
        "Family animation pool.",
    ),
    _PresetCard(
        PRESET_DARK_THRILLER_CRIME,
        "Мрачный криминал",
        "Dark crime",
        "Криминал, триллеры, нуар.",
        "Crime and thriller pool.",
    ),
)


_PRESET_CARDS_BY_KEY = {card.key: card for card in _PRESET_CARDS}


@dataclass(frozen=True)
class _PresetVisual:
    accent: str
    icon_filename: str


_PRESET_ICON_DIR = Path(__file__).resolve().parents[1] / "images" / "logos_for_start_select_menu" / "split_icons"

_PRESET_VISUALS: dict[str, _PresetVisual] = {
    PRESET_MANUAL: _PresetVisual("#18CDEB", "manual.png"),
    PRESET_HOLLYWOOD_MAINSTREAM: _PresetVisual("#E0B24A", "hollywood_mainstream.png"),
    PRESET_RUSSIAN_MAINSTREAM: _PresetVisual("#3A9DFF", "russian_mainstream.png"),
    PRESET_ANIME: _PresetVisual("#9A5CFF", "anime.png"),
    PRESET_K_DRAMA: _PresetVisual("#F06AB6", "k_drama.png"),
    PRESET_TURKISH_DRAMAS: _PresetVisual("#F39A38", "turkish_dramas.png"),
    PRESET_BRITISH_EUROPEAN_DETECTIVE: _PresetVisual("#61D17D", "british_european_detective.png"),
    PRESET_FAMILY_ANIMATION: _PresetVisual("#32D6D2", "family_animation.png"),
    PRESET_DARK_THRILLER_CRIME: _PresetVisual("#F0475C", "dark_thriller_crime.png"),
}

_GENRE_GROUP_LABELS: dict[str, tuple[str, str]] = {
    "action_adventure": ("Боевик и приключения", "Action & adventure"),
    "adventure": ("Приключения", "Adventure"),
    "anime": ("Аниме", "Anime"),
    "drama": ("Драма", "Drama"),
    "romance": ("Мелодрама", "Romance"),
    "comedy": ("Комедия", "Comedy"),
    "crime": ("Криминал", "Crime"),
    "detective": ("Детектив", "Detective"),
    "family": ("Семейный", "Family"),
    "fantasy": ("Фантастика и фэнтези", "Sci-fi & fantasy"),
    "horror": ("Ужасы", "Horror"),
    "mystery": ("Мистика", "Mystery"),
    "thriller": ("Триллер", "Thriller"),
}

_MOJIBAKE_MARKERS = (
    "\u0420\u00a0",
    "\u0420\u0459",
    "\u0420\u045f",
    "\u0420\u040e",
    "\u0420\u045c",
    "\u0420\u2019",
    "\u0420\u045e",
    "\u0420\u201c",
    "\u0420\u00b0",
    "\u0420\u00b5",
    "\u0420\u0451",
    "\u0420\u00bb",
    "\u0421\u0403",
    "\u0421\u201a",
    "\u0421\u040a",
    "\u0421\u040f",
    "\u0421\u2018",
    "\u0421\u2020",
    "\u0432\u0402",
)


def _repair_mojibake(text: str) -> str:
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return text
    try:
        repaired = text.encode("cp1251").decode("utf-8")
    except UnicodeError:
        return text
    return repaired or text


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
        key="country_selection",
        title_ru="Какие страны ищем?",
        title_en="Which countries should Watchbane search?",
        options=(),
    ),
    _Question(
        key="animation_mode",
        title_ru="Как относимся к анимации?",
        title_en="How should animation be handled?",
        options=(
            (ANIMATION_MODE_ANY, "Не важно", "No preference"),
            (ANIMATION_MODE_ANIMATION_ONLY, "Только анимация", "Animation only"),
            (ANIMATION_MODE_LIVE_ACTION_ONLY, "Без анимации", "Live action only"),
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
)


def _color(hex_color: str, alpha: float = 1.0) -> QColor:
    color = QColor(hex_color)
    color.setAlpha(max(0, min(255, int(round(float(alpha) * 255)))))
    return color


class _PresetCardButton(QAbstractButton):
    """Painted preset tile matching the startup reference screen."""

    def __init__(self, *, title: str, description: str, visual: _PresetVisual, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("onboardingPresetCard")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setText(f"{title}\n{description}")
        self._title = title
        self._description = description
        self._visual = visual
        self._icon = QPixmap(str(_PRESET_ICON_DIR / visual.icon_filename))
        self.setMinimumHeight(scale_px(96))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(scale_px(704), scale_px(96))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(scale_px(280), scale_px(96))

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        del event
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )

        rect = QRectF(self.rect()).adjusted(scale_px(1), scale_px(1), -scale_px(1), -scale_px(1))
        radius = scale_px(10)
        hover = self.underMouse()
        checked = self.isChecked()

        tint_alpha = 0.075 if checked else 0.038 if hover else 0.02
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, _color(self._visual.accent, tint_alpha))
        gradient.setColorAt(0.22, QColor("#0F1B2B"))
        gradient.setColorAt(1.0, QColor("#091523"))

        card_path = QPainterPath()
        card_path.addRoundedRect(rect, radius, radius)
        painter.fillPath(card_path, QBrush(gradient))

        if checked:
            border = _color(self._visual.accent, 0.62)
        elif hover:
            border = _color(self._visual.accent, 0.30)
        else:
            border = QColor("#1D314A")
        painter.setPen(QPen(border, scale_px(1)))
        painter.drawPath(card_path)

        strip_rect = QRectF(rect.left(), rect.top() + scale_px(2), scale_px(2), rect.height() - scale_px(4))
        strip_path = QPainterPath()
        strip_path.addRoundedRect(strip_rect, scale_px(2), scale_px(2))
        painter.fillPath(strip_path, _color(self._visual.accent, 0.58))

        icon_size = scale_px(52)
        icon_rect = QRectF(
            rect.left() + scale_px(22),
            rect.center().y() - icon_size / 2,
            icon_size,
            icon_size,
        )
        if not self._icon.isNull():
            painter.save()
            painter.setOpacity(0.68 if checked or hover else 0.58)
            painter.drawPixmap(icon_rect.toRect(), self._icon)
            painter.restore()

        text_left = rect.left() + scale_px(94)
        text_right_pad = scale_px(62 if checked else 24)
        text_width = max(scale_px(80), int(rect.right() - text_left - text_right_pad))

        title_font = QFont(FONT_FAMILY)
        title_font.setPixelSize(font_px(19))
        title_font.setWeight(QFont.Weight.Bold)
        description_font = QFont(FONT_FAMILY)
        description_font.setPixelSize(font_px(16))
        description_font.setWeight(QFont.Weight.Medium)

        title_rect = QRectF(text_left, rect.top() + scale_px(20), text_width, scale_px(30))
        desc_rect = QRectF(text_left, rect.top() + scale_px(52), text_width, scale_px(26))
        self._draw_text(painter, title_rect, self._title, title_font, QColor("#F3F7FF"))
        self._draw_text(painter, desc_rect, self._description, description_font, QColor("#AEBBD0"))

        if checked:
            self._draw_checkmark(painter, rect)

    def _draw_text(self, painter: QPainter, rect: QRectF, text: str, font: QFont, color: QColor) -> None:
        painter.setFont(font)
        painter.setPen(color)
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width()))
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

    def _draw_checkmark(self, painter: QPainter, rect: QRectF) -> None:
        diameter = scale_px(26)
        center_x = rect.right() - scale_px(36)
        center_y = rect.center().y()
        circle = QRectF(center_x - diameter / 2, center_y - diameter / 2, diameter, diameter)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color("#19AEEB", 0.88))
        painter.drawEllipse(circle)

        pen = QPen(QColor("#F6FBFF"), scale_px(2))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(
            int(center_x - scale_px(7)),
            int(center_y),
            int(center_x - scale_px(2)),
            int(center_y + scale_px(6)),
        )
        painter.drawLine(
            int(center_x - scale_px(2)),
            int(center_y + scale_px(6)),
            int(center_x + scale_px(8)),
            int(center_y - scale_px(7)),
        )


def _wizard_style() -> str:
    return f"""
QDialog#onboardingAutofillDialog {{
    background-color: #06101C;
    font-family: {FONT_FAMILY_QSS};
}}
QFrame#onboardingCard {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #0B1B2D,
        stop:0.48 #0A1828,
        stop:1 #071321
    );
    border: 1px solid #1D334C;
    border-radius: {px(20)}px;
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
    color: #25C6FF;
    font-size: {font_px(18)}px;
    font-weight: 700;
}}
QLabel#onboardingTitle {{
    background-color: transparent;
    border: 0;
    color: {COLOR_TEXT};
    font-size: {font_px(32)}px;
    font-weight: 750;
}}
QLabel#onboardingSubtitle, QLabel#onboardingStatus {{
    background-color: transparent;
    border: 0;
    color: #AEBBD0;
    font-size: {font_px(17)}px;
}}
QLabel#onboardingDot {{
    background-color: transparent;
    border: 0;
    color: #6F7F94;
    font-size: {font_px(16)}px;
}}
QLabel#onboardingDot[active="true"] {{
    color: #18CDEB;
    font-size: {font_px(FONT_DIALOG_TITLE)}px;
}}
QLabel#onboardingDot[state="done"] {{
    color: #18CDEB;
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
    background-color: {COLOR_ACCENT_SOFT};
    border-color: {COLOR_ACCENT};
    color: {COLOR_TEXT};
}}
QPushButton#onboardingOption:checked:focus {{
    border-color: {COLOR_ACCENT};
}}
QScrollArea#onboardingPresetScroll,
QScrollArea#onboardingPresetScroll QWidget#onboardingPresetViewport {{
    background-color: transparent;
    border: 0;
}}
QScrollArea#onboardingPresetScroll QScrollBar:vertical {{
    background-color: #0A1624;
    border: 1px solid #1D334C;
    border-radius: {px(5)}px;
    width: {px(12)}px;
    margin: 0;
}}
QScrollArea#onboardingPresetScroll QScrollBar::handle:vertical {{
    background-color: #1E4B78;
    border-radius: {px(5)}px;
    min-height: {px(82)}px;
}}
QScrollArea#onboardingPresetScroll QScrollBar::handle:vertical:hover {{
    background-color: #2EA8FF;
}}
QScrollArea#onboardingPresetScroll QScrollBar::add-line:vertical,
QScrollArea#onboardingPresetScroll QScrollBar::sub-line:vertical {{
    height: 0;
    background: transparent;
    border: 0;
}}
QScrollArea#onboardingPresetScroll QScrollBar::add-page:vertical,
QScrollArea#onboardingPresetScroll QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QWidget#onboardingCountryChipHost {{
    background-color: transparent;
    border: 0;
}}
QPushButton#onboardingCountryChip {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_DIALOG_TITLE)}px;
    font-weight: 650;
    padding: {px(12)}px {px(16)}px;
    min-height: {px(48)}px;
}}
QPushButton#onboardingCountryChip:hover {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_BORDER_HOVER};
}}
QPushButton#onboardingCountryChip:checked {{
    background-color: {COLOR_ACCENT_SOFT};
    border-color: {COLOR_ACCENT};
    color: {COLOR_TEXT};
}}
QPushButton#onboardingNext, QPushButton#onboardingOpen {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #25C6FF, stop:1 #159FE3);
    border: 1px solid #25C6FF;
    border-radius: {px(9)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_DIALOG_TITLE - 1)}px;
    font-weight: 700;
    padding: {px(9)}px {px(20)}px;
    min-width: {px(232)}px;
}}
QPushButton#onboardingNext:hover, QPushButton#onboardingOpen:hover {{
    background-color: #25C6FF;
    border-color: #25C6FF;
}}
QPushButton#onboardingNext:disabled {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_BORDER};
    color: {COLOR_TEXT_MUTED};
}}
QPushButton#onboardingBack, QPushButton#onboardingSkip {{
    background-color: rgba(16, 27, 43, 190);
    border: 1px solid #2A3D57;
    border-radius: {px(9)}px;
    color: #AEBBD0;
    font-size: {font_px(FONT_DIALOG_TITLE - 1)}px;
    font-weight: 650;
    padding: {px(9)}px {px(16)}px;
}}
QPushButton#onboardingBack:hover, QPushButton#onboardingSkip:hover {{
    background-color: #132337;
    border-color: #3A567A;
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
QLabel#onboardingFinalSummary {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(12)}px {px(14)}px;
}}
QFrame#onboardingScalePreview {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
}}
QLabel#onboardingScalePreviewHeader {{
    background-color: transparent;
    border: 0;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_DIALOG_TITLE)}px;
    font-weight: 750;
}}
QLabel#onboardingScalePreviewMeta {{
    background-color: transparent;
    border: 0;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
}}
QLabel#onboardingScalePreviewChip {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 650;
    padding: {px(6)}px {px(10)}px;
}}
QPushButton#onboardingScalePreviewAction {{
    background-color: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 700;
    padding: {px(9)}px {px(14)}px;
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
        self._answers: dict[str, Any] = {}
        self._apply_preset_defaults(PRESET_MANUAL)
        self._question_pages: list[tuple[_Question, QWidget, QButtonGroup]] = []
        self._preset_group: QButtonGroup | None = None
        self._worker: OnboardingAutofillWorker | None = None
        self._page_animation: QParallelAnimationGroup | None = None
        self._progress_animation: QPropertyAnimation | None = None
        self._last_result: dict[str, Any] = {}

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(scale_px(16), scale_px(20), scale_px(16), scale_px(19))
        root_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("onboardingCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root_layout.addWidget(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            scale_px(46),
            scale_px(34),
            scale_px(46),
            scale_px(34),
        )
        card_layout.setSpacing(scale_px(SPACING_MEDIUM))

        self._dots = QWidget()
        self._dots.setObjectName("onboardingDots")
        self._dots_layout = QHBoxLayout(self._dots)
        self._dots_layout.setContentsMargins(0, 0, 0, 0)
        self._dots_layout.setSpacing(scale_px(8))
        card_layout.addWidget(self._dots)

        self._stack = QStackedWidget()
        self._stack.setObjectName("onboardingStack")
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout.addWidget(self._stack, 1)

        self._setup_page = self._build_setup_page()
        self._stack.addWidget(self._setup_page)
        self._preset_page = self._build_preset_page()
        self._stack.addWidget(self._preset_page)
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
        self._back_button.setMinimumSize(scale_px(128), scale_px(52))
        self._back_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._back_button.clicked.connect(self._go_back)
        controls.addWidget(self._back_button)
        self._footer_skip_button = QPushButton("Пропустить" if self._ui_language == "ru" else "Skip")
        self._footer_skip_button.setObjectName("onboardingSkip")
        self._footer_skip_button.setMinimumSize(scale_px(176), scale_px(52))
        self._footer_skip_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._footer_skip_button.clicked.connect(self._skip)
        controls.addWidget(self._footer_skip_button)
        controls.addStretch(1)
        self._next_button = QPushButton("Далее" if self._ui_language == "ru" else "Next")
        self._next_button.setObjectName("onboardingNext")
        self._next_button.setMinimumSize(scale_px(272), scale_px(52))
        self._next_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
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

    def _current_preset_key(self) -> str:
        key = str(self._answers.get("taste_preset") or PRESET_MANUAL).strip()
        return key if key in _PRESET_CARDS_BY_KEY else PRESET_MANUAL

    def _preset_title(self, key: str) -> str:
        card = _PRESET_CARDS_BY_KEY.get(key) or _PRESET_CARDS_BY_KEY[PRESET_MANUAL]
        return self._text(card.title_ru, card.title_en)

    def _apply_preset_defaults(self, key: str) -> None:
        preset_key = str(key or PRESET_MANUAL).strip()
        self._answers["taste_preset"] = preset_key if preset_key in _PRESET_CARDS_BY_KEY else PRESET_MANUAL
        preset = get_taste_preset(self._answers["taste_preset"])
        if preset is None:
            self._answers.update({
                "country_selection": list(ONBOARDING_COUNTRY_DEFAULT),
                "media_preference": "both",
                "animation_mode": ANIMATION_MODE_ANY,
                "release_preference": "mixed",
                "vibe_preference": "mixed",
            })
            return
        self._answers.update({
            "country_selection": list(preset.countries[:ONBOARDING_COUNTRY_PICKER_LIMIT]),
            "media_preference": preset.media_type,
            "animation_mode": preset.animation_mode,
            "release_preference": preset.release_preference,
            "vibe_preference": preset.vibe,
        })

    def _locked_question_keys(self) -> set[str]:
        if self._current_preset_key() == PRESET_MANUAL:
            return set()
        return {"country_selection", "animation_mode"}

    def _active_questions(self) -> list[_Question]:
        locked = self._locked_question_keys()
        return [question for question in _QUESTIONS if question.key not in locked]

    def _text(self, ru: str, en: str) -> str:
        return en if self._ui_language == "en" else _repair_mojibake(ru)

    def _country_name(self, code: str) -> str:
        labels = (
            country_reference.ENGLISH_COUNTRY_NAME_BY_ISO2
            if self._ui_language == "en"
            else country_reference.COUNTRY_NAME_BY_ISO2
        )
        normalized = str(code or "").strip().upper()
        return labels.get(normalized, normalized)

    def _country_names(self, *codes: str) -> str:
        return " + ".join(self._country_name(code) for code in codes)

    def _normalized_country_answers(self, value: Any = None) -> list[str]:
        raw = self._answers.get("country_selection") if value is None else value
        if raw in (None, ""):
            raw = ONBOARDING_COUNTRY_DEFAULT
        if isinstance(raw, str):
            items = [part.strip() for part in raw.replace(",", " ").split()]
        elif isinstance(raw, (list, tuple, set)):
            items = list(raw)
        else:
            items = []
        selected: list[str] = []
        preset = get_taste_preset(self._current_preset_key())
        preset_countries = tuple(preset.countries) if preset is not None else ()
        allowed = set(ONBOARDING_COUNTRY_CODES) | set(preset_countries)
        for item in items:
            code = str(item or "").strip().upper()
            if code in allowed and code not in selected:
                selected.append(code)
            if len(selected) >= ONBOARDING_COUNTRY_PICKER_LIMIT:
                break
        return selected or list(ONBOARDING_COUNTRY_DEFAULT)

    def _country_option_codes(self) -> tuple[str, ...]:
        result: list[str] = []
        for code in [*self._selected_country_codes(), *ONBOARDING_COUNTRY_CODES]:
            normalized = str(code or "").strip().upper()
            if normalized and normalized not in result:
                result.append(normalized)
            if len(result) >= ONBOARDING_COUNTRY_PICKER_LIMIT:
                break
        return tuple(result)

    def _selected_country_codes(self) -> list[str]:
        return self._normalized_country_answers()

    def _question_start_index(self) -> int:
        return 2

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
        layout.setSpacing(scale_px(SPACING_MEDIUM))

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
            button.setMinimumHeight(scale_px(48))
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
            button.setMinimumHeight(scale_px(48))
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setChecked(abs(value - self._ui_scale) < 0.01)
            self._scale_group.addButton(button)
            scale_row.addWidget(button)
        self._scale_group.buttonClicked.connect(self._on_scale_selected)
        layout.addLayout(scale_row)

        self._scale_preview = QFrame()
        self._scale_preview.setObjectName("onboardingScalePreview")
        self._scale_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        preview_layout = QVBoxLayout(self._scale_preview)
        preview_layout.setContentsMargins(scale_px(12), scale_px(10), scale_px(12), scale_px(10))
        preview_layout.setSpacing(scale_px(SPACING_SMALL - 1))

        self._scale_preview_title = QLabel("")
        self._scale_preview_title.setObjectName("onboardingScalePreviewHeader")
        self._scale_preview_title.setWordWrap(True)
        preview_layout.addWidget(self._scale_preview_title)

        preview_middle = QHBoxLayout()
        preview_middle.setContentsMargins(0, 0, 0, 0)
        preview_middle.setSpacing(scale_px(SPACING_MEDIUM))
        self._scale_preview_meta = QLabel("")
        self._scale_preview_meta.setObjectName("onboardingScalePreviewMeta")
        self._scale_preview_meta.setWordWrap(True)
        self._scale_preview_meta.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        preview_middle.addWidget(self._scale_preview_meta, 1)
        preview_layout.addLayout(preview_middle)

        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(scale_px(SPACING_SMALL))
        self._scale_preview_chips: list[QLabel] = []
        for _ in range(3):
            chip = QLabel("")
            chip.setObjectName("onboardingScalePreviewChip")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setMinimumHeight(scale_px(24))
            chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            self._scale_preview_chips.append(chip)
            chips_row.addWidget(chip)
        chips_row.addStretch(1)
        self._scale_preview_action = QPushButton("")
        self._scale_preview_action.setObjectName("onboardingScalePreviewAction")
        self._scale_preview_action.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scale_preview_action.setMinimumHeight(scale_px(32))
        chips_row.addWidget(self._scale_preview_action)
        preview_layout.addLayout(chips_row)
        layout.addWidget(self._scale_preview)
        layout.addStretch(1)
        self._update_setup_text()
        return page

    def _build_preset_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("onboardingPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, scale_px(6), 0, 0)
        layout.setSpacing(scale_px(SPACING_MEDIUM))

        eyebrow = QLabel(self._text("Стартовый пресет", "Starter preset"))
        eyebrow.setObjectName("onboardingEyebrow")
        layout.addWidget(eyebrow)

        title = QLabel(self._text("Выберите направление пула", "Choose the starter pool direction"))
        title.setObjectName("onboardingTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        subtitle = QLabel(self._text(
            "Пресет задаёт страны, тип медиа, анимацию и вайб. На следующих шагах всё можно изменить.",
            "A preset fills countries, media type, animation mode and vibe. You can edit everything next.",
        ))
        subtitle.setObjectName("onboardingSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setObjectName("onboardingPresetScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        viewport = QWidget()
        viewport.setObjectName("onboardingPresetViewport")
        viewport.setMinimumHeight(scale_px(760))
        grid = QGridLayout(viewport)
        grid.setContentsMargins(0, scale_px(6), scale_px(12), 0)
        grid.setHorizontalSpacing(scale_px(14))
        grid.setVerticalSpacing(scale_px(12))
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._preset_group = QButtonGroup(self)
        self._preset_group.setExclusive(True)
        for index, card in enumerate(_PRESET_CARDS):
            visual = _PRESET_VISUALS.get(card.key, _PRESET_VISUALS[PRESET_MANUAL])
            button = _PresetCardButton(
                title=self._text(card.title_ru, card.title_en),
                description=self._text(card.description_ru, card.description_en),
                visual=visual,
            )
            button.setProperty("answer", card.key)
            button.setProperty("preset_key", card.key)
            button.setChecked(card.key == self._current_preset_key())
            self._preset_group.addButton(button)
            grid.addWidget(button, index // 2, index % 2)
        self._preset_group.buttonClicked.connect(self._on_preset_selected)

        scroll.setWidget(viewport)
        layout.addWidget(scroll, 1)
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
        if hasattr(self, "_scale_preview_title"):
            percent = int(round(float(self._ui_scale) * 100))
            self._scale_preview_title.setText(self._text(
                f"Пример карточки на {percent}%",
                f"Sample card at {percent}%",
            ))
            self._scale_preview_meta.setText(self._text(
                "Так будут выглядеть текст, чипы и кнопка.",
                "This is how text, chips and buttons will look.",
            ))
            self._scale_preview_meta.setVisible(float(self._ui_scale) < 1.30)
            self._scale_preview_action.setText(self._text("Кнопка", "Button"))
            chip_labels = (
                ("Страна", "Жанр", "Оценка")
                if self._ui_language == "ru"
                else ("Country", "Genre", "Score")
            )
            for chip, text in zip(self._scale_preview_chips, chip_labels, strict=True):
                chip.setText(text)

    def _on_language_selected(self, button: QPushButton) -> None:
        value = str(button.property("answer") or "").strip().casefold()
        if value not in {"ru", "en"} or value == self._ui_language:
            return
        self._ui_language = value
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
        self.setStyleSheet(_wizard_style())
        self._update_setup_text()

    def _rebuild_question_and_result_pages(self) -> None:
        current = self._stack.currentIndex()
        while self._stack.count() > 1:
            widget = self._stack.widget(1)
            self._stack.removeWidget(widget)
            widget.deleteLater()
        self._question_pages.clear()
        self._preset_page = self._build_preset_page()
        self._stack.addWidget(self._preset_page)
        self._rebuild_edit_pages(current_index=current)

    def _rebuild_edit_pages(self, *, current_index: int | None = None) -> None:
        current = self._stack.currentIndex() if current_index is None else current_index
        while self._stack.count() > self._question_start_index():
            widget = self._stack.widget(self._question_start_index())
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
        layout.setSpacing(scale_px(SPACING_MEDIUM))

        eyebrow = QLabel(self._text("Стартовая настройка", "Starter setup"))
        eyebrow.setObjectName("onboardingEyebrow")
        layout.addWidget(eyebrow)

        title = QLabel(self._text(question.title_ru, question.title_en))
        title.setObjectName("onboardingTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        subtitle = QLabel(self._text(
            "Выберите одну или несколько стран, чтобы собрать первый пул."
            if question.key == "country_selection"
            else "Выберите один вариант, чтобы собрать первый пул.",
            "Choose one or more countries to build the first pool."
            if question.key == "country_selection"
            else "Choose one option to build the first pool.",
        ))
        subtitle.setObjectName("onboardingSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        group = QButtonGroup(self)
        group.setExclusive(question.key != "country_selection")
        group.buttonClicked.connect(lambda _button, key=question.key: self._on_option_selected(key))

        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(0, scale_px(SPACING_SMALL), 0, 0)
        options_layout.setSpacing(scale_px(SPACING_MEDIUM))
        if question.key == "country_selection":
            selected_countries = set(self._selected_country_codes())
            chips_host = QWidget()
            chips_host.setObjectName("onboardingCountryChipHost")
            flow = FlowLayout(
                chips_host,
                margin=0,
                h_spacing=scale_px(SPACING_SMALL),
                v_spacing=scale_px(SPACING_SMALL),
            )
            chips_host.setLayout(flow)
            for code in self._country_option_codes():
                button = QPushButton(self._country_name(code))
                button.setObjectName("onboardingCountryChip")
                button.setCheckable(True)
                button.setProperty("answer", code)
                button.setMinimumHeight(scale_px(48))
                button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
                button.setChecked(code in selected_countries)
                group.addButton(button)
                flow.addWidget(button)
            options_layout.addWidget(chips_host)
        else:
            selected_value = str(self._answers.get(question.key) or "").strip()
            for value, label_ru, label_en in question.options:
                button = QPushButton(self._text(label_ru, label_en))
                button.setObjectName("onboardingOption")
                button.setCheckable(True)
                button.setProperty("answer", value)
                button.setMinimumHeight(scale_px(58))
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                button.setChecked(value == selected_value)
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
        layout.setSpacing(scale_px(SPACING_MEDIUM))

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
        layout.setSpacing(scale_px(SPACING_MEDIUM))

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
        layout.addWidget(
            watchbane_wordmark_label(scale_px(220), scale_px(44)),
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addSpacing(scale_px(SPACING_SMALL))

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addStretch(1)
        self._skip_button = QPushButton(self._text("Пропустить", "Skip"))
        self._skip_button.setObjectName("onboardingSkip")
        self._skip_button.clicked.connect(self._skip)
        actions.addWidget(self._skip_button)
        self._open_button = QPushButton(self._text("Открыть рекомендации", "Open Recommendations"))
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
        layout.setSpacing(scale_px(SPACING_MEDIUM))

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
        self._final_open_button = QPushButton(self._text("Открыть рекомендации", "Open Recommendations"))
        self._final_open_button.setObjectName("onboardingOpen")
        self._final_open_button.clicked.connect(self._finish)
        actions.addWidget(self._final_open_button)
        layout.addLayout(actions)
        return page

    def _answer_label(self, key: str, value: Any) -> str:
        normalized = str(value or "").strip()
        for question in _QUESTIONS:
            if question.key != key:
                continue
            for option_value, label_ru, label_en in question.options:
                if option_value == normalized:
                    return self._text(label_ru, label_en)
        return normalized or "-"

    def _genre_groups_line(self, genre_groups: Any) -> str:
        labels = [
            self._text(*_GENRE_GROUP_LABELS[str(group)])
            for group in (genre_groups or ())
            if str(group) in _GENRE_GROUP_LABELS
        ]
        if labels:
            return ", ".join(labels)
        return self._text("все", "all")

    def _format_plan_summary(self) -> str:
        profile = self._profile()
        plan = candidate_service.get_onboarding_autofill_plan_view(profile)
        quotas = plan.get("quotas") or {}
        media = quotas.get("media_type") or {}
        release = quotas.get("release") or {}
        vibe = quotas.get("vibe") or {}
        preset_key = str(profile.get("taste_preset") or PRESET_MANUAL)
        country_plan = plan.get("country_plan") if isinstance(plan.get("country_plan"), dict) else {}
        country_counts = country_plan or quotas.get("country") or {}
        country_line = ", ".join(
            f"{self._country_name(country)}: {int(count)}"
            for country, count in country_counts.items()
        )
        lines = [
            self._text(
                f"Пресет: {self._preset_title(preset_key)} ({preset_key})",
                f"Preset: {self._preset_title(preset_key)} ({preset_key})",
            ),
            self._text(
                f"Медиа: {self._answer_label('media_preference', profile.get('media_preference'))}",
                f"Media: {self._answer_label('media_preference', profile.get('media_preference'))}",
            ),
            self._text(
                f"Анимация: {self._answer_label('animation_mode', profile.get('animation_mode'))}",
                f"Animation: {self._answer_label('animation_mode', profile.get('animation_mode'))}",
            ),
            self._text(
                f"Релиз: {self._answer_label('release_preference', profile.get('release_preference'))}",
                f"Release: {self._answer_label('release_preference', profile.get('release_preference'))}",
            ),
            self._text(
                f"Вайб: {self._answer_label('vibe_preference', profile.get('vibe_preference'))}",
                f"Vibe: {self._answer_label('vibe_preference', profile.get('vibe_preference'))}",
            ),
            self._text(
                f"Жанры: {self._genre_groups_line(profile.get('genre_groups'))}",
                f"Genres: {self._genre_groups_line(profile.get('genre_groups'))}",
            ),
            self._text(f"Цель: {plan.get('target')} кандидатов", f"Target: {plan.get('target')} candidates"),
            self._text(f"Страны: {country_line or '-'}", f"Countries: {country_line or '-'}"),
            self._text(f"Фильмы: {media.get('movie', 0)}, сериалы: {media.get('tv', 0)}", f"Movies: {media.get('movie', 0)}, series: {media.get('tv', 0)}"),
            self._text(
                f"Классика: {release.get('classic_sweep', 0)}, новинки: {release.get('new_sweep', 0)}, топ: {release.get('top_all_time', 0)}",
                f"Classics: {release.get('classic_sweep', 0)}, new: {release.get('new_sweep', 0)}, top: {release.get('top_all_time', 0)}",
            ),
            self._text(f"Лёгкий вайб: {vibe.get('light', 0)}, мрачный: {vibe.get('dark', 0)}", f"Light vibe: {vibe.get('light', 0)}, dark: {vibe.get('dark', 0)}"),
        ]
        lines.append(self._text(f"Срезов поиска: {plan.get('bucket_count')}", f"Search slices: {plan.get('bucket_count')}"))
        return "\n".join(lines)

    def _update_plan_summary(self) -> None:
        if hasattr(self, "_plan_summary_label"):
            self._plan_summary_label.setText(self._format_plan_summary())

    def _format_actual_line(self, label_ru: str, label_en: str, key: str, planned: dict, actual: dict) -> str:
        planned_counts = planned.get(key) if isinstance(planned.get(key), dict) else {}
        actual_counts = actual.get(key) if isinstance(actual.get(key), dict) else {}
        keys = list(planned_counts)
        for value in actual_counts:
            if value not in keys:
                keys.append(value)
        display_key = self._country_name if key == "country" else str
        parts = [
            f"{display_key(value)}: {int(actual_counts.get(value, 0))}/{int(planned_counts.get(value, 0))}"
            for value in keys
        ]
        label = self._text(label_ru, label_en)
        return f"{label}: {', '.join(parts) if parts else '-'}"

    def _localized_warning_text(self, warning: str) -> str:
        if self._ui_language != "ru":
            return warning
        lines = []
        for line in str(warning or "").splitlines():
            text = line.strip()
            match = re.fullmatch(r"Starter pool underfilled: created (\d+) of (\d+)\.", text)
            if match:
                lines.append(f"Стартовый пул собран не полностью: {match.group(1)} из {match.group(2)}.")
                continue
            match = re.fullmatch(r"Only (\d+) candidates collected; the pool can be topped up later\.", text)
            if match:
                lines.append(f"Собрано только {match.group(1)} кандидатов; пул можно пополнить позже.")
                continue
            match = re.fullmatch(r"Media quota underfilled: ([^ ]+) planned (\d+), actual (\d+)\.", text)
            if match:
                lines.append(f"Недобор media-квоты: {match.group(1)} план {match.group(2)}, факт {match.group(3)}.")
                continue
            match = re.fullmatch(r"Country quota underfilled: ([^ ]+) planned (\d+), actual (\d+)\.", text)
            if match:
                lines.append(f"Недобор страны: {match.group(1)} план {match.group(2)}, факт {match.group(3)}.")
                continue
            match = re.fullmatch(r"Origin quota underfilled: ([^ ]+) planned (\d+), actual (\d+)\.", text)
            if match:
                lines.append(f"Недобор origin-квоты: {match.group(1)} план {match.group(2)}, факт {match.group(3)}.")
                continue
            match = re.fullmatch(r"Rejected future/unreleased titles: (\d+)\.", text)
            if match:
                lines.append(f"Отклонено будущих/невышедших релизов: {match.group(1)}.")
                continue
            lines.append(text)
        return "\n".join(line for line in lines if line)

    def _format_result_summary(self, data: dict[str, Any], *, created: int, failed: bool) -> str:
        planned = data.get("planned_counts") if isinstance(data.get("planned_counts"), dict) else {}
        actual = data.get("actual_counts") if isinstance(data.get("actual_counts"), dict) else {}
        api_requests = int(data.get("api_requests") or 0)
        rejected_future = int(data.get("rejected_future_count") or 0)
        if failed or created == 0:
            lines = [
                self._text(
                    "Кандидаты не добавлены. Можно открыть приложение без стартового пула или повторить сборку.",
                    "No candidates were added. You can open the app without a starter pool or retry.",
                )
            ]
        else:
            lines = [
                self._text(
                    f"Добавлено кандидатов: {created}. Следующий шаг — открыть вкладку кандидатов.",
                    f"Candidates added: {created}. Next step: open the Recommendations tab.",
                )
            ]
        if planned or actual:
            lines.append(self._format_actual_line("Факт/план страны", "Actual/planned countries", "country", planned, actual))
            lines.append(self._format_actual_line("Факт/план media", "Actual/planned media", "media_type", planned, actual))
        details = self._text(
            f"API-запросов: {api_requests}, отклонено будущих релизов: {rejected_future}",
            f"API requests: {api_requests}, future releases rejected: {rejected_future}",
        )
        lines.append(details)
        warning = str(data.get("warning") or "").strip()
        if warning:
            lines.append(self._localized_warning_text(warning))
        return "\n".join(lines)

    def _rebuild_dots(self) -> None:
        while self._dots_layout.count():
            item = self._dots_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        current_index = self._stack.currentIndex()
        for index in range(self._stack.count()):
            dot = QLabel("●")
            dot.setObjectName("onboardingDot")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setProperty("active", "true" if index == current_index else "false")
            dot.setProperty("state", "done" if index < current_index else ("active" if index == current_index else "pending"))
            dot.style().unpolish(dot)
            dot.style().polish(dot)
            self._dots_layout.addWidget(dot)
        self._dots_layout.addStretch(1)

    def _set_page(self, index: int) -> None:
        previous_index = self._stack.currentIndex()
        self._stack.setCurrentIndex(index)
        if index == self._plan_index():
            self._update_plan_summary()
        if index != previous_index:
            self._animate_current_page(forward=index >= previous_index)
        self._rebuild_dots()
        self._sync_controls()

    def _animate_current_page(self, *, forward: bool = True) -> None:
        widget = self._stack.currentWidget()
        if widget is None:
            return
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            widget.setGraphicsEffect(None)
            return
        if self._page_animation is not None:
            self._page_animation.stop()
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        fade = QPropertyAnimation(effect, b"opacity", self)
        fade.setDuration(200)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        end_pos = widget.pos()
        offset = scale_px(28) if forward else -scale_px(28)
        slide = QPropertyAnimation(widget, b"pos", self)
        slide.setDuration(200)
        slide.setStartValue(QPoint(end_pos.x() + offset, end_pos.y()))
        slide.setEndValue(end_pos)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(fade)
        group.addAnimation(slide)
        group.finished.connect(lambda: widget.setGraphicsEffect(None))
        self._page_animation = group
        group.start()

    def _selected_answer(self, question: _Question, group: QButtonGroup) -> Any:
        if question.key == "country_selection":
            selected = [
                str(button.property("answer") or "").strip().upper()
                for button in group.buttons()
                if button.isChecked()
            ]
            return self._normalized_country_answers(selected) if selected else None
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

    def _on_preset_selected(self, button: QAbstractButton) -> None:
        preset_key = str(button.property("answer") or PRESET_MANUAL).strip()
        self._apply_preset_defaults(preset_key)
        self._sync_controls()

    def _on_option_selected(self, key: str) -> None:
        current = self._current_question()
        if current is None:
            return
        question, group = current
        if question.key != key:
            return
        selected = self._selected_answer(question, group)
        if selected is not None:
            self._answers[key] = selected
        else:
            self._answers.pop(key, None)
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
        on_preset = index == 1
        on_plan = index == self._plan_index()
        self._next_button.setEnabled(
            on_setup
            or on_preset
            or on_plan
            or (current is not None and self._selected_answer(current[0], current[1]) is not None)
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
        if index == 1:
            self._rebuild_edit_pages(current_index=self._question_start_index())
            return
        if index == self._plan_index():
            self._start_autofill()
            return
        current = self._current_question()
        if current is None:
            return
        question, group = current
        selected = self._selected_answer(question, group)
        if selected is None:
            return
        self._answers[question.key] = selected
        next_index = self._stack.currentIndex() + 1
        self._set_page(next_index)

    def _country_selection_payload(self) -> dict[str, Any]:
        countries = self._selected_country_codes()
        weight = 1.0 / len(countries)
        return {
            "mode": "single_country" if len(countries) == 1 else "multi_country",
            "home_country": "RU" if self._ui_language == "ru" else "US",
            "selected_countries": countries,
            "country_weights": {country: weight for country in countries},
            "exclude_home_country": False,
            "max_countries": ONBOARDING_COUNTRY_PICKER_LIMIT,
            "primary_country": countries[0],
            "secondary_country": countries[1] if len(countries) > 1 else None,
        }

    def _profile(self) -> dict[str, Any]:
        countries = set(self._selected_country_codes())
        if self._ui_language == "ru":
            if countries == {"RU"}:
                origin_preference = "domestic"
            elif "RU" in countries:
                origin_preference = "mixed"
            else:
                origin_preference = "foreign"
        else:
            origin_preference = None
        preset = get_taste_preset(self._current_preset_key())
        genre_groups = list(preset.genre_groups) if preset is not None else []
        return {
            "taste_preset": self._current_preset_key(),
            "ui_language": self._ui_language,
            "media_preference": self._answers.get("media_preference") or "both",
            "animation_mode": self._answers.get("animation_mode") or ANIMATION_MODE_ANY,
            "release_preference": self._answers.get("release_preference") or "mixed",
            "vibe_preference": self._answers.get("vibe_preference") or "mixed",
            "origin_preference": origin_preference,
            "country_selection": self._country_selection_payload(),
            "genre_groups": genre_groups,
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
        self._set_progress_smooth(value)

    def _set_progress_smooth(self, value: int) -> None:
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            self._progress.setValue(value)
            return
        if value <= self._progress.value():
            self._progress.setValue(value)
            return
        if self._progress_animation is not None:
            self._progress_animation.stop()
        animation = QPropertyAnimation(self._progress, b"value", self)
        animation.setDuration(260)
        animation.setStartValue(self._progress.value())
        animation.setEndValue(value)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._progress_animation = animation
        animation.start()

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
            self._warning_label.setText(self._localized_warning_text(str(warning)))
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
        if failed or created == 0:
            self._final_title.setText(self._text("Пул не собран", "Pool was not built"))
            self._retry_button.setVisible(True)
        else:
            self._final_title.setText(self._text("Пул кандидатов готов", "Candidate pool is ready"))
            self._retry_button.setVisible(False)
        self._final_summary.setText(self._format_result_summary(data, created=created, failed=failed))
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
