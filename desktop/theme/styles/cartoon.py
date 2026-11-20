"""Light two-section shell. Local styling; legacy theme implementations remain."""
from desktop.theme.scaling import layout_px as px, font_px


def build_cartoon_style():
    return f'''
    QWidget {{ background: #FFF7E8; color: #25272C; font-size: {font_px(14)}px; }}
    QLabel {{ background: transparent; border: none; }}
    QMainWindow, QStackedWidget, QScrollArea {{ background: #FFF7E8; border: none; }}
    QTabWidget::pane {{ border: none; top: 0px; }}
    QTabBar::tab {{ background: #FFF7E8; color: #25272C; border: 2px solid #25272C; border-radius: {px(12)}px; padding: {px(10)}px {px(24)}px; margin: {px(5)}px; font-weight: 700; }}
    QTabBar::tab:selected {{ background: #FFB84D; }}
    QPushButton {{ background: #FFFDF5; color: #25272C; border: 2px solid #25272C; border-bottom-width: 3px; border-radius: {px(11)}px; padding: {px(7)}px {px(12)}px; }}
    QPushButton:hover, QPushButton:checked {{ background: #FFB84D; }}
    QPushButton:focus {{ border: 3px solid #25272C; background: #FFE1A9; }}
    QPushButton:disabled {{ color: #77756F; border-color: #ABA396; }}
    QLineEdit, QComboBox {{ background: #FFFDF5; color: #25272C; border: 2px solid #25272C; border-radius: {px(14)}px; padding: {px(12)}px; selection-background-color: #FFB84D; selection-color: #25272C; }}
    QLineEdit:focus {{ border: 3px solid #25272C; }}
    QFrame#storyCard, QFrame#collectionCard {{ background: #FFFDF5; border: 2px solid #25272C; border-bottom-width: 4px; border-radius: {px(15)}px; }}
    QWidget#storyCardBody, QWidget#storyDetails {{ background: transparent; }}
    QLabel#storyHeading {{ font-size: {font_px(30)}px; font-weight: 800; }}
    QLabel#storyTitle {{ font-size: {font_px(21)}px; font-weight: 750; }}
    QLabel#storyMuted {{ color: #615D55; font-size: {font_px(12)}px; }}
    QLabel#storyEvidence {{ color: #25272C; font-size: {font_px(15)}px; }}
    QLabel#storyPoster {{ background: #FFE1A9; color: #615D55; border: 1px dashed #25272C; border-radius: {px(9)}px; font-size: {font_px(10)}px; }}
    QPushButton#storySearchButton {{ background: #FFB84D; font-weight: 750; padding: {px(12)}px {px(20)}px; }}
    QFrame#storyCard QPushButton, QFrame#collectionCard QPushButton {{ padding: {px(5)}px {px(9)}px; font-size: {font_px(12)}px; }}
    QFrame#storyCard QPushButton#storySaveAction:disabled {{ background: #E6EFCA; color: #37441D; border-color: #778656; }}
    QPushButton#storyExample {{ background: #FFF7E8; border: 1px solid #B8AD99; color: #615D55; }}
    QPushButton#storyExample:hover {{ background: #FFE1A9; color: #25272C; }}
    QScrollBar:vertical {{ background: #FFF7E8; width: {px(9)}px; border: none; }}
    QScrollBar::handle:vertical {{ background: #C6BCA9; min-height: {px(24)}px; border-radius: {px(4)}px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QToolTip {{ background: #FFFDF5; color: #25272C; border: 1px solid #25272C; }}
    QStatusBar {{ background: #FFF7E8; color: #615D55; border: none; }}
    '''
