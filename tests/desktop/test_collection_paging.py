import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton

from desktop.collection.view import CollectionView
from desktop.theme.scaling import get_ui_scale, set_ui_scale


LONG_PLOT = 'Герой пытается раскрыть тайну незнакомого города. ' * 25


class StubLibrary:
    _action_candidates_by_key = {}

    def __init__(self):
        self._entries = [
            (str(i), {}, {'title': f'История {i:03d}', 'overview': LONG_PLOT})
            for i in range(121)
        ]

    def _switch_section(self, section, **kwargs):
        self._library_section = section

    def reload_entries(self, **kwargs):
        pass


@pytest.mark.parametrize('scale', [1.0, 1.25])
def test_collection_bounds_page_and_searches_entire_library(qtbot, scale):
    was = get_ui_scale()
    set_ui_scale(scale)
    try:
        library = StubLibrary()
        view = CollectionView(library)
        qtbot.addWidget(view.widget)
        view.widget.resize(920, 720)
        view.widget.show()

        def cards():
            return view.cards.findChildren(QFrame, 'collectionCard')

        def button_click(button):
            qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

        assert len(cards()) == view.PAGE_SIZE == 24
        assert view.status.text() == 'Историй: 121'
        assert not view.previous_page.isEnabled()
        synopsis = cards()[0].findChild(QLabel, 'storyEvidence')
        disclosure = next(b for b in cards()[0].findChildren(QPushButton)
                          if b.text() == 'Полный сюжет')
        assert len(synopsis.text()) <= 211
        button_click(disclosure)
        assert synopsis.text() == LONG_PLOT and disclosure.isChecked()
        assert len(cards()[1].findChild(QLabel, 'storyEvidence').text()) <= 211
        button_click(disclosure)
        assert synopsis.text().endswith('…')

        button_click(view.next_page)
        assert view.page_status.text() == '2 из 6'
        assert len(cards()) == 24
        assert cards()[0].findChild(QLabel, 'storyTitle').text() == 'История 024'

        view.search.setText('120')
        assert len(cards()) == 1
        assert cards()[0].findChild(QLabel, 'storyTitle').text() == 'История 120'
        assert not view.pager.isVisible()
        view.search.clear()
        assert view.page_status.text() == '1 из 6'
        assert len(cards()) == 24

        for _ in range(5):
            button_click(view.next_page)
        assert len(cards()) == 1
        assert not view.next_page.isEnabled()
        library._entries.pop()
        view.reload_entries()
        assert view.page_status.text() == '5 из 5'
        assert len(cards()) == 24
    finally:
        set_ui_scale(was)
