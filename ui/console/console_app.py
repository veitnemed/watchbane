"""Консольный entry flow приложения."""

from functools import partial

from common import valid
from storage import files as storage_files
from ui.console import global_menu
from ui.console import menu_state
from ui.console import request
from ui.console import ui


def run_console_app():
    """Запускает главный цикл консольного приложения."""
    storage_files.init_all_dates()

    while True:
        ui.clean_terminal()
        _data, movies_counter = menu_state.get_menu_state()
        candidate_summary = menu_state.get_candidate_summary_view()
        ui.show_global_menu(movies_counter, candidate_summary=candidate_summary)

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 5)])
        if command == "0":
            break
        elif command == "1":
            global_menu.open_maintenance_menu()
        elif command == "2":
            global_menu.open_watched_menu()
        elif command == "3":
            global_menu.open_candidate_pool_menu()
        elif command == "4":
            global_menu.open_search_menu()
        elif command == "5":
            global_menu.open_reference_menu()
