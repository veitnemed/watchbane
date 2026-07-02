"""QSS builders for analytics tab."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403

def build_analytics_style(
    *,
    font_base: int = FONT_BASE,
    font_page_title: int = FONT_TITLE,
    font_subtitle: int = FONT_BASE,
    font_section_title: int = FONT_SECTION,
    font_summary_label: int = FONT_SMALL,
    font_summary_value: int = FONT_KPI_VALUE,
    font_insight: int = FONT_BASE,
    font_dense_count: int = FONT_BASE,
    font_dense_score: int = FONT_DENSE_SCORE,
    font_same_score_titles: int = FONT_SMALL,
    font_fallback: int = FONT_BASE,
) -> str:
    """Return the analytics tab stylesheet."""
    return f"""
QWidget#analyticsRoot {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: {FONT_FAMILY_QSS};
    font-size: {font_base}px;
}}
QWidget#modelRoot {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: {FONT_FAMILY_QSS};
    font-size: {font_base}px;
}}
QWidget#analyticsBarRow {{
    background: transparent;
}}
QLabel#analyticsTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_page_title}px;
    font-weight: 700;
}}
QLabel#modelTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_page_title}px;
    font-weight: 700;
}}
QLabel#analyticsSubtitle {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_subtitle}px;
}}
QLabel#modelSubtitle {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_subtitle}px;
}}
QFrame#summaryCard,
QFrame#analyticsSection,
QFrame#insightCard,
QFrame#sameScoreCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QFrame#chartConstructorControls {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
    padding: 10px;
}}
QWidget#chartConstructorField {{
    background: transparent;
}}
QLabel#chartConstructorLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_summary_label}px;
    font-weight: 600;
}}
QComboBox#chartConstructorCombo {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    color: {COLOR_TEXT};
    font-size: {font_base}px;
    padding: 8px 12px;
    min-height: 20px;
}}
QComboBox#chartConstructorCombo:focus {{
    border-color: {COLOR_ACCENT};
}}
QComboBox#chartConstructorCombo::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox#chartConstructorCombo QAbstractItemView {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_ACCENT_SOFT};
}}
QPushButton#chartConstructorBuildButton {{
    background-color: {COLOR_ACCENT_SOFT};
    border: 1px solid {COLOR_ACCENT};
    border-radius: {RADIUS_BUTTON}px;
    color: {COLOR_TEXT};
    font-size: {font_base}px;
    font-weight: 700;
    padding: 9px 14px;
}}
QPushButton#chartConstructorBuildButton:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
QFrame#summaryCardStale {{
    background-color: {COLOR_STALE_BG};
    border: 1px solid {COLOR_STALE_BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QFrame#summaryCardStale QLabel#summaryValue {{
    color: {COLOR_STALE_TEXT};
}}
QFrame#modelStaleBanner {{
    background-color: {COLOR_STALE_BG};
    border: 1px solid {COLOR_STALE_BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QLabel#modelStaleBannerText {{
    background: transparent;
    color: {COLOR_STALE_TEXT};
    font-size: {font_base}px;
    font-weight: 600;
}}
QPushButton#modelTrainButton {{
    background-color: {COLOR_ADD_BUTTON};
    border: 1px solid {COLOR_ADD_BUTTON_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    color: {COLOR_TEXT};
    font-size: {font_base}px;
    font-weight: 600;
    padding: 10px 16px;
}}
QPushButton#modelTrainButton:hover:enabled {{
    background-color: {COLOR_ADD_BUTTON_HOVER};
    border-color: {COLOR_ADD_BUTTON_HOVER};
}}
QPushButton#modelTrainButton:disabled {{
    background-color: {COLOR_CARD_ALT};
    border-color: {COLOR_BORDER};
    color: {COLOR_TEXT_MUTED};
}}
QPushButton#modelDetailsButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_base}px;
    font-weight: 600;
    padding: 10px 16px;
}}
QPushButton#modelDetailsButton:hover:enabled {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
    color: {COLOR_TEXT};
}}
QFrame#modelWeightsPanel {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QLabel#modelWeightsText {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: {font_summary_label}px;
}}
QLabel#modelTrainingStatus {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_base}px;
}}
QLabel#modelTrainingResult {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_base}px;
}}
QProgressBar#modelTrainingProgress {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BAR}px;
    height: 14px;
    text-align: center;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_summary_label}px;
}}
QProgressBar#modelTrainingProgress::chunk {{
    background-color: {COLOR_ACCENT};
    border-radius: {RADIUS_BAR}px;
}}
QFrame#summaryIconBadge,
QFrame#sectionHeaderIconBadge {{
    background-color: {COLOR_ACCENT_SOFT};
    border: 1px solid {COLOR_ACCENT};
    border-radius: 18px;
}}
QLabel#summaryIcon,
QLabel#sectionHeaderIcon {{
    background: transparent;
    color: {COLOR_ACCENT_PLOT_HOVER};
    font-size: 15px;
    font-weight: 700;
}}
QWidget#sectionHeader,
QWidget#insightRow {{
    background: transparent;
}}
QLabel#summaryLabel,
QLabel#barLabel,
QLabel#denseLabel,
QLabel#denseTitles {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_summary_label}px;
}}
QLabel#insightBullet {{
    background: transparent;
    color: {COLOR_ACCENT};
    font-size: 10px;
}}
QLabel#insightText {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_insight}px;
}}
QLabel#summaryValue {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_summary_value}px;
    font-weight: 700;
}}
QLabel#sectionTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_section_title}px;
    font-weight: 700;
}}
QLabel#sectionHeaderMenu {{
    background: transparent;
    color: {COLOR_TEXT_MUTED};
    font-size: 18px;
    font-weight: 700;
    padding: 0 2px;
}}
QLabel#completenessHeadline {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_insight}px;
    font-weight: 600;
}}
QLabel#completenessSubline {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_summary_label}px;
}}
QFrame#barTrack {{
    background-color: {COLOR_CARD_ALT};
    border-radius: {RADIUS_BAR}px;
}}
QFrame#barFill {{
    background-color: {COLOR_ACCENT};
    border-radius: {RADIUS_BAR}px;
}}
QLabel#barCount,
QLabel#denseCount {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_dense_count}px;
    font-weight: 600;
}}
QLabel#denseScore {{
    background: transparent;
    color: {COLOR_ACCENT};
    font-size: {font_dense_score}px;
    font-weight: 700;
}}
QFrame#denseScoreBadge {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BUTTON}px;
}}
QLabel#sameScoreTitles {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_same_score_titles}px;
}}
QLabel#analyticsFallback {{
    background: transparent;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_fallback}px;
    padding: 8px 2px;
}}
QWebEngineView#analyticsPlotlyChart {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_BAR}px;
}}
QPushButton#analyticsListExpand {{
    background: transparent;
    border: none;
    color: {COLOR_ACCENT_PLOT_HOVER};
    font-size: {font_summary_label}px;
    font-weight: 600;
    padding: 2px 0;
    text-align: left;
}}
QPushButton#analyticsListExpand:hover {{
    color: {COLOR_ACCENT_HOVER};
}}
"""
