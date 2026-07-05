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
    font_base = font_px(font_base)
    font_page_title = font_px(font_page_title)
    font_subtitle = font_px(font_subtitle)
    font_section_title = font_px(font_section_title)
    font_summary_label = font_px(font_summary_label)
    font_summary_value = font_px(font_summary_value)
    font_insight = font_px(font_insight)
    font_dense_count = font_px(font_dense_count)
    font_dense_score = font_px(font_dense_score)
    font_same_score_titles = font_px(font_same_score_titles)
    font_fallback = font_px(font_fallback)
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
    border-radius: {px(RADIUS_CARD)}px;
}}
QFrame#chartConstructorControls {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
    padding: {px(10)}px;
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
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_base}px;
    padding: {px(8)}px {px(12)}px;
    min-height: {px(20)}px;
}}
QComboBox#chartConstructorCombo:focus {{
    border-color: {COLOR_FOCUS_BORDER};
}}
QComboBox#chartConstructorCombo::drop-down {{
    border: none;
    width: {px(24)}px;
}}
QComboBox#chartConstructorCombo QAbstractItemView {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_SELECTED_BG};
}}
QPushButton#chartConstructorBuildButton {{
    background-color: {COLOR_ACCENT_SOFT};
    border: 1px solid {COLOR_ACCENT};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_base}px;
    font-weight: 700;
    padding: {px(9)}px {px(14)}px;
}}
QPushButton#chartConstructorBuildButton:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
QFrame#summaryCardStale {{
    background-color: {COLOR_STALE_BG};
    border: 1px solid {COLOR_STALE_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
}}
QFrame#summaryCardStale QLabel#summaryValue {{
    color: {COLOR_STALE_TEXT};
}}
QFrame#modelStaleBanner {{
    background-color: {COLOR_STALE_BG};
    border: 1px solid {COLOR_STALE_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
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
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_base}px;
    font-weight: 600;
    padding: {px(10)}px {px(16)}px;
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
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT_SOFT};
    font-size: {font_base}px;
    font-weight: 600;
    padding: {px(10)}px {px(16)}px;
}}
QPushButton#modelDetailsButton:hover:enabled {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
    color: {COLOR_TEXT};
}}
QFrame#modelWeightsPanel {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
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
    border-radius: {px(RADIUS_BAR)}px;
    height: {px(14)}px;
    text-align: center;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_summary_label}px;
}}
QProgressBar#modelTrainingProgress::chunk {{
    background-color: {COLOR_ACCENT};
    border-radius: {px(RADIUS_BAR)}px;
}}
QFrame#summaryIconBadge,
QFrame#sectionHeaderIconBadge {{
    background-color: {COLOR_ACCENT_SOFT};
    border: 1px solid {COLOR_ACCENT};
    border-radius: {px(18)}px;
}}
QLabel#summaryIcon,
QLabel#sectionHeaderIcon {{
    background: transparent;
    color: {COLOR_ACCENT_PLOT_HOVER};
    font-size: {font_px(15)}px;
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
    font-size: {font_px(10)}px;
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
    font-size: {font_px(18)}px;
    font-weight: 700;
    padding: 0 {px(2)}px;
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
    border-radius: {px(RADIUS_BAR)}px;
}}
QFrame#barFill {{
    background-color: {COLOR_ACCENT};
    border-radius: {px(RADIUS_BAR)}px;
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
    border-radius: {px(RADIUS_BUTTON)}px;
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
    padding: {px(8)}px {px(2)}px;
}}
QWebEngineView#analyticsPlotlyChart {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BAR)}px;
}}
QPushButton#analyticsListExpand {{
    background: transparent;
    border: none;
    color: {COLOR_ACCENT_PLOT_HOVER};
    font-size: {font_summary_label}px;
    font-weight: 600;
    padding: {px(2)}px 0;
    text-align: left;
}}
QPushButton#analyticsListExpand:hover {{
    color: {COLOR_ACCENT_HOVER};
}}
"""
