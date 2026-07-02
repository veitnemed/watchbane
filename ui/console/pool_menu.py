"""Console menus for candidate pool viewing, cleanup, and import flows."""

from functools import partial

from candidates import service as candidate_service
from common import valid
from ui.console import candidate_pool_tools
from ui.console import interface_funcs
from ui.console import menu_state
from ui.console import request
from ui.console import search_menu
from ui.console import tmdb_pool_tools
from ui.console import ui


def open_candidate_pool_menu() -> None:
    """Open candidate pool menu with maintenance before generation flows."""
    while True:
        ui.clean_terminal()
        _data, movies_counter = menu_state.get_menu_state()
        pool_stats_view = candidate_service.get_pool_stats_view()
        ui.show_candidate_pool_menu(movies_counter, pool_stats_view["summary"])

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 5)])
        if command == "0":
            return
        if command == "1":
            candidate_pool_tools.show_candidate_pool()
        elif command == "2":
            search_menu.show_global_candidate_search()
        elif command == "3":
            interface_funcs.mark_candidate_as_watched()
        elif command == "4":
            open_candidate_pool_cleanup_menu()
        elif command == "5":
            open_candidate_pool_import_menu()

        try:
            ui.press_enter()
        except KeyboardInterrupt:
            print("\nВозвращаюсь в меню.")


def open_candidate_pool_cleanup_menu() -> None:
    """Open maintenance and diagnostics actions for the common candidate pool."""
    while True:
        ui.clean_terminal()
        ui.show_candidate_pool_cleanup_menu()

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 13)])
        if command == "0":
            return

        try:
            if command == "1":
                candidate_pool_tools.show_candidate_pool()
            elif command == "2":
                candidate_pool_tools.clean_common_pool_duplicates()
            elif command == "3":
                candidate_pool_tools.purge_pool_dataset_title_matches()
            elif command == "4":
                candidate_pool_tools.show_suspicious_candidate_duplicates()
            elif command == "5":
                candidate_pool_tools.show_cross_year_candidate_duplicates()
            elif command == "6":
                candidate_pool_tools.show_title_candidate_duplicates()
            elif command == "7":
                candidate_pool_tools.show_candidate_poster_diagnostics()
            elif command == "8":
                candidate_pool_tools.start_candidate_pool_preview_poster_job()
            elif command == "9":
                candidate_pool_tools.show_candidate_pool_preview_poster_job_status()
            elif command == "10":
                candidate_pool_tools.show_candidate_pool_preview_poster_job_log()
            elif command == "11":
                candidate_pool_tools.stop_candidate_pool_preview_poster_job()
            elif command == "12":
                candidate_pool_tools.download_candidate_pool_preview_posters()
            elif command == "13":
                candidate_pool_tools.show_candidate_metadata_diagnostics()
        except KeyboardInterrupt:
            print("\nДействие прервано. Возвращаюсь в меню.")

        try:
            ui.press_enter()
        except KeyboardInterrupt:
            print("\nВозвращаюсь в меню.")


def open_candidate_pool_import_menu() -> None:
    """Open rare pool creation/import actions away from the first screen."""
    while True:
        ui.clean_terminal()
        ui.show_candidate_pool_import_menu()

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 3)])
        if command == "0":
            return
        if command == "1":
            tmdb_pool_tools.run_tmdb_candidate_pool_flow()
        elif command == "2":
            tmdb_pool_tools.import_tmdb_result_to_common_pool_flow()
        elif command == "3":
            candidate_pool_tools.edit_candidate_pool_filters()

        ui.press_enter()


def open_candidate_pool_management_menu() -> None:
    """Compatibility wrapper for the old pool management menu name."""
    open_candidate_pool_import_menu()


def open_candidate_pool_diagnostics_menu() -> None:
    """Compatibility wrapper for the old pool diagnostics menu name."""
    open_candidate_pool_cleanup_menu()
