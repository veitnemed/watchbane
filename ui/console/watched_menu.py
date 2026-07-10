"""Console menu for watched dataset operations."""

from functools import partial

from common import valid
from ui.console import backup_menu
from ui.console import interface_funcs
from ui.console import menu_state
from ui.console import request
from ui.console import ui


def open_watched_menu() -> None:
    """Open watched dataset menu with add/edit actions below maintenance actions."""
    while True:
        ui.clean_terminal()
        _data, movies_counter = menu_state.get_menu_state()
        ui.show_watched_menu(movies_counter)

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 4)])
        if command == "0":
            return
        if command == "1":
            interface_funcs.show_all_movies()
        elif command == "2":
            interface_funcs.rename_movie_record()
        elif command == "3":
            interface_funcs.delete_watched_record()
        elif command == "4":
            interface_funcs.request_object()

        ui.press_enter()


def open_watched_backup_menu() -> None:
    """Compatibility helper for maintenance data/backup section."""
    backup_menu.open_backup_menu()
