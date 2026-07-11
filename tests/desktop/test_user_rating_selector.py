from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
import inspect

from desktop.shared.widgets.user_rating_selector import UserRatingSelector


def test_user_rating_selector_returns_int_and_supports_keyboard(qtbot) -> None:
    selector = UserRatingSelector()
    qtbot.addWidget(selector)
    selector.show()

    assert selector.value() is None
    QTest.keyClick(selector, Qt.Key.Key_2)
    assert selector.value() == 2
    assert isinstance(selector.value(), int)
    selector.clear()
    assert selector.value() is None


def test_rating_dialog_sources_do_not_use_double_spinbox() -> None:
    from desktop.watched.add_title.preview_dialog import AddTitlePreviewDialog
    from desktop.watched.dialogs.score_edit import ScoreEditDialog

    assert "QDoubleSpinBox" not in inspect.getsource(AddTitlePreviewDialog)
    assert "QDoubleSpinBox" not in inspect.getsource(ScoreEditDialog)
