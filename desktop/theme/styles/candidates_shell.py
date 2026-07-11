"""QSS for the Candidates filters and list tabs."""

from __future__ import annotations

from desktop.theme.tokens import *  # noqa: F403


def build_candidates_shell_style() -> str:
    """Return stylesheet for candidate search filters and list."""
    return f"""
QLineEdit#candidateListSearch {{
    font-size: {font_px(FONT_SECTION)}px;
    padding: {px(INPUT_PADDING_Y + 1)}px {px(INPUT_PADDING_X + 2)}px;
    min-height: {px(34)}px;
}}
QWidget#candidateSearchSidebar {{
    background: transparent;
}}
QLabel#candidateSearchHeader {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_TITLE)}px;
    font-weight: 700;
}}
QLabel#candidateSearchSubtitle {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
    line-height: 1.32;
}}
QFrame#candidateFiltersIntro {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(10)}px;
}}
QLabel#candidateFiltersSummaryTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 700;
}}
QLabel#candidateFiltersSummaryTitleIcon {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER_HOVER};
    border-radius: {px(13)}px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 700;
    padding: 0;
}}
QLabel#candidateFiltersIntroLead {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
    line-height: 1.35;
}}
QLabel#candidateFiltersIntroStats {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE + 1)}px;
    font-weight: 600;
}}
QProgressBar#candidateReplenishProgressBar {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER_ACTIVE};
    border-radius: {px(8)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 700;
    min-height: {px(18)}px;
    max-height: {px(18)}px;
    text-align: center;
}}
QProgressBar#candidateReplenishProgressBar::chunk {{
    background-color: {COLOR_ADD_BUTTON_TOP};
    border-radius: {px(7)}px;
    margin: {px(2)}px;
}}
QFrame#candidateFiltersSummaryRow {{
    background: transparent;
    min-height: {px(26)}px;
}}
QLabel#candidateFiltersSummaryRowIcon {{
    background: transparent;
    color: {COLOR_TEXT_MUTED};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
}}
QLabel#candidateFiltersSummaryRowLabel {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QLabel#candidateFiltersSummaryRowValue {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QFrame#candidateFiltersSummaryDivider {{
    background-color: {COLOR_DIVIDER};
    border: none;
    min-height: {px(1)}px;
    max-height: {px(1)}px;
}}
QLabel#candidateSearchHint {{
    background: transparent;
    color: {COLOR_TEXT_MUTED};
    font-size: {font_px(FONT_TINY)}px;
}}
QLabel#candidateSearchResultsSummary,
QLabel#candidateSearchDetailPlaceholder,
QLabel#candidateSearchExplanation {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
}}
QLabel#candidateSearchFieldLabel {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
    padding: {px(2)}px 0 0 0;
}}
QComboBox#candidateSearchMediaType,
QComboBox#simplePreferenceMedia,
QComboBox#simplePreferenceCollection,
QComboBox#simplePreferenceOrigin,
QComboBox#simplePreferenceMood,
QComboBox#candidateReplenishPreset,
QComboBox#candidateReplenishAnimationMode,
QComboBox#candidateReplenishVibe,
QComboBox#candidateReplenishReleasePreference,
QComboBox#candidateReplenishOriginPreference {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(8)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(5)}px {px(9)}px;
    min-height: {px(28)}px;
}}
QComboBox#candidateSearchMediaType:focus,
QComboBox#simplePreferenceMedia:focus,
QComboBox#simplePreferenceCollection:focus,
QComboBox#simplePreferenceOrigin:focus,
QComboBox#simplePreferenceMood:focus,
QComboBox#candidateReplenishPreset:focus,
QComboBox#candidateReplenishAnimationMode:focus,
QComboBox#candidateReplenishVibe:focus,
QComboBox#candidateReplenishReleasePreference:focus,
QComboBox#candidateReplenishOriginPreference:focus {{
    border: 1px solid {COLOR_FOCUS_BORDER};
}}
QComboBox#candidateSearchMediaType::drop-down,
QComboBox#simplePreferenceMedia::drop-down,
QComboBox#simplePreferenceCollection::drop-down,
QComboBox#simplePreferenceOrigin::drop-down,
QComboBox#simplePreferenceMood::drop-down,
QComboBox#candidateReplenishPreset::drop-down,
QComboBox#candidateReplenishAnimationMode::drop-down,
QComboBox#candidateReplenishVibe::drop-down,
QComboBox#candidateReplenishReleasePreference::drop-down,
QComboBox#candidateReplenishOriginPreference::drop-down {{
    border: none;
    width: {px(26)}px;
}}
QComboBox#candidateSearchMediaType::down-arrow,
QComboBox#simplePreferenceMedia::down-arrow,
QComboBox#simplePreferenceCollection::down-arrow,
QComboBox#simplePreferenceOrigin::down-arrow,
QComboBox#simplePreferenceMood::down-arrow,
QComboBox#candidateReplenishPreset::down-arrow,
QComboBox#candidateReplenishAnimationMode::down-arrow,
QComboBox#candidateReplenishVibe::down-arrow,
QComboBox#candidateReplenishReleasePreference::down-arrow,
QComboBox#candidateReplenishOriginPreference::down-arrow {{
    width: {px(10)}px;
    height: {px(10)}px;
}}
QListView#candidateListWidget {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    padding: {px(8)}px;
    outline: none;
}}
QListView#candidateListWidget::item {{
    padding: 0;
    border: none;
    margin: {px(1)}px 0;
    background: transparent;
}}
QListView#candidateListWidget::item:selected {{
    background: transparent;
    color: {COLOR_TEXT};
}}
QListView#candidateListWidget::item:hover {{
    background: transparent;
}}
QLabel#candidateListCounter {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    padding: 0 {px(4)}px;
}}
QLabel#recommendationsDeckStatus {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
    padding: 0 {px(4)}px;
}}
QPushButton#recommendationsNewDeckButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER_HOVER};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 600;
    min-height: {px(30)}px;
    padding: {px(4)}px {px(12)}px;
}}
QPushButton#recommendationsNewDeckButton:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_FOCUS_BORDER};
}}
QFrame#recommendationActionPanel {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER_HOVER};
    border-radius: {px(8)}px;
}}
QLabel#recommendationReasonsTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 700;
}}
QLabel#recommendationReasonsText {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QPushButton#recommendationWatchedButton,
QPushButton#recommendationWatchlistButton,
QPushButton#recommendationHiddenButton {{
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 700;
    min-height: {px(34)}px;
    padding: {px(5)}px {px(10)}px;
}}
QPushButton#recommendationWatchedButton {{
    background-color: {COLOR_ADD_BUTTON_TOP};
    border: 1px solid {COLOR_FOCUS_BORDER};
    color: {COLOR_TEXT};
}}
QPushButton#recommendationWatchlistButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER_HOVER};
    color: {COLOR_TEXT};
}}
QPushButton#recommendationHiddenButton {{
    background-color: transparent;
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT_SECONDARY};
}}
QPushButton#recommendationWatchedButton:hover,
QPushButton#recommendationWatchlistButton:hover,
QPushButton#recommendationHiddenButton:hover {{
    border-color: {COLOR_FOCUS_BORDER};
}}
QWidget#candidateSortRow {{
    background: transparent;
}}
QLabel#candidateSortLabel {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
}}
QComboBox#candidateListSort {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_INPUT)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    padding: {px(INPUT_PADDING_Y)}px {px(INPUT_PADDING_X)}px;
    min-height: {px(20)}px;
    max-width: {px(160)}px;
}}
QComboBox#candidateListSort:focus {{
    border: 1px solid {COLOR_FOCUS_BORDER};
}}
QComboBox#candidateListSort::drop-down {{
    border: none;
    width: {px(28)}px;
}}
QComboBox#candidateListSort::down-arrow {{
    width: {px(10)}px;
    height: {px(10)}px;
}}
QWidget#candidateFiltersRoot {{
    font-size: {font_px(FONT_BASE)}px;
}}
QScrollArea#candidateSearchFiltersScroll,
QWidget#candidateSearchFiltersHost {{
    background: transparent;
}}
QFrame#candidateFilterSection {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(10)}px;
}}
QFrame#candidateSimplePreferencesSection {{
    background-color: {COLOR_MOOD_SURFACE};
    border: 1px solid {COLOR_MOOD_BORDER};
    border-radius: {px(10)}px;
}}
QLabel#candidateSimplePreferencesLead {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_SMALL)}px;
}}
QFrame#candidateFilterSection:hover {{
    border-color: {COLOR_BORDER_HOVER};
}}
QLabel#candidateFilterSectionTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SECTION)}px;
    font-weight: 700;
    padding: 0;
}}
QLabel#candidateFilterSectionBadge {{
    background-color: {COLOR_ACCENT_SOFT};
    border: 1px solid {COLOR_BORDER_ACTIVE};
    border-radius: {px(8)}px;
    color: {COLOR_ACCENT_HOVER};
    font-size: {font_px(FONT_SMALL)}px;
    font-weight: 700;
    padding: 0;
}}
QToolButton#candidateAdvancedFiltersToggle,
QToolButton#candidateRecommendationAdvancedModeToggle {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
    padding: {px(6)}px {px(10)}px;
    min-height: {px(30)}px;
}}
QToolButton#candidateAdvancedFiltersToggle:hover,
QToolButton#candidateRecommendationAdvancedModeToggle:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
QWidget#candidateAdvancedFiltersContent,
QWidget#candidateAdvancedFiltersGroup {{
    background: transparent;
}}
QLabel#candidateAdvancedFiltersGroupTitle {{
    background: transparent;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 700;
    padding: 0;
}}
QFrame#candidateFilterDivider {{
    background-color: {COLOR_DIVIDER};
    border: none;
    min-height: {px(1)}px;
    max-height: {px(1)}px;
}}
QPushButton#candidateSearchApplyTopButton {{
    background-color: {COLOR_ADD_BUTTON};
    border: 1px solid {COLOR_ADD_BUTTON_BORDER};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE + 1)}px;
    font-weight: 600;
    padding: {px(7)}px {px(14)}px;
    min-height: {px(38)}px;
    max-height: {px(42)}px;
}}
QPushButton#candidateSearchApplyTopButton:hover {{
    background-color: {COLOR_ADD_BUTTON_HOVER};
}}
QPushButton#candidateSearchResetTopButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON_SMALL)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE + 1)}px;
    font-weight: 600;
    padding: {px(7)}px {px(14)}px;
    min-height: {px(38)}px;
    max-height: {px(42)}px;
}}
QPushButton#candidateSearchResetTopButton:hover {{
    background-color: {COLOR_CONTROL_HOVER};
    border-color: {COLOR_BORDER_HOVER};
}}
QCheckBox#candidateReplenishEnabled,
QCheckBox#candidateReplenishAdvancedOverride {{
    background: transparent;
    color: {COLOR_TEXT_SECONDARY};
    font-size: {font_px(FONT_BASE)}px;
    spacing: {px(8)}px;
    min-height: {px(30)}px;
}}
QCheckBox#candidateReplenishEnabled::indicator,
QCheckBox#candidateReplenishAdvancedOverride::indicator {{
    width: {px(18)}px;
    height: {px(18)}px;
}}
QPushButton#candidateSearchButton,
QPushButton#candidateSearchAddWatched {{
    background-color: {COLOR_ADD_BUTTON};
    border: 1px solid {COLOR_ADD_BUTTON_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_BASE)}px;
    font-weight: 600;
    padding: {px(10)}px {px(16)}px;
    min-height: {px(40)}px;
}}
QPushButton#candidateSearchButton:hover,
QPushButton#candidateSearchAddWatched:hover {{
    background-color: {COLOR_ADD_BUTTON_HOVER};
}}
QPushButton#candidateSearchWatchlist,
QPushButton#candidateSearchHide {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_BUTTON)}px;
    color: {COLOR_TEXT};
    font-size: {font_px(FONT_SMALL)}px;
    padding: {px(8)}px {px(12)}px;
}}
QPushButton#candidateSearchWatchlist:hover,
QPushButton#candidateSearchHide:hover {{
    background-color: {COLOR_CONTROL_HOVER};
}}
QFrame#candidateSearchDetailCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {px(RADIUS_CARD)}px;
}}
"""
