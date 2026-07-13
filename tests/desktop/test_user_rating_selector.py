import inspect

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QLabel

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


def test_score_edit_dialog_keeps_field_label_visible(qtbot) -> None:
    from desktop.watched.dialogs.score_edit import ScoreEditDialog

    entry = (
        "example",
        {"main_info": {"title": "Example", "year": 2024}},
        {"title": "Example", "year": 2024, "user_score": 2},
    )
    dialog = ScoreEditDialog(entry)
    qtbot.addWidget(dialog)
    dialog.show()

    field_label = dialog.findChild(QLabel, "scoreEditFieldLabel")

    assert field_label is not None
    assert field_label.isVisible() is True
    assert field_label.width() > 0
