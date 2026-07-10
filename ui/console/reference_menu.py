"""Console menu for dataset genre reference."""

from functools import partial

from common import valid
from ui.console import genre_menu
from ui.console import request
from ui.console import ui


def open_reference_menu() -> None:
    """Open reference data menu."""
    while True:
        ui.clean_terminal()
        ui.show_reference_menu()

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 1)])
        if command == "0":
            return
        if command == "1":
            genre_menu.show_dataset_genre_catalog()

        ui.press_enter()
