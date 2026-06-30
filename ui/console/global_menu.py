"""Содержит циклы главного меню и подменю приложения."""

from functools import partial

from config import constant
from dataset import excel_work
from storage import files as storage_files
from dataset import storage_movie
from candidates import service as candidate_service
from ui.console import backup_menu
from ui.console import interface_funcs
from ui.console import menu_state
from ui.console import request
from ui.console import search_menu
from ui.console import genre_menu
from ui.console import tags_menu
from ui.console import ui
from common import valid


def open_data_menu():
    """Открывает меню работы с данными."""
    while True:
        ui.clean_terminal()
        data, movies_counter = menu_state.get_menu_state()
        ui.show_data_menu(movies_counter)

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 8)])
        if command == "0":
            return
        if command == "1":
            if excel_work.export_dataset_to_excel(overwrite=True):
                storage_files.open_file(constant.EDIT_EXCEL)
        elif command == "2":
            excel_work.replace_dataset_from_excel()
        elif command == "3":
            interface_funcs.request_object()
        elif command == "4":
            interface_funcs.show_all_movies()
        elif command == "5":
            interface_funcs.show_data_info()
        elif command == "6":
            backup_menu.open_backup_menu()
        elif command == "7":
            interface_funcs.rename_movie_record()
        elif command == "8":
            interface_funcs.delete_watched_record()

        ui.press_enter()


def open_genres_menu():
    """Открывает меню жанров."""
    while True:
        ui.clean_terminal()
        ui.show_genres_menu()

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 1)])
        if command == "0":
            return
        if command == "1":
            genre_menu.show_dataset_genre_catalog()

        ui.press_enter()


def open_extra_menu():
    """Открывает дополнительное меню."""
    while True:
        ui.clean_terminal()
        data, movies_counter = menu_state.get_menu_state()
        ui.show_extra_menu(movies_counter)

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 9)])
        if command == "0":
            return
        if command == "1":
            interface_funcs.show_api_features()
        elif command == "2":
            interface_funcs.show_dataset_genres()
        elif command == "3":
            interface_funcs.search_sql_title_by_name()
        elif command == "4":
            interface_funcs.sync_watched_descriptions_and_posters()
        elif command == "5":
            interface_funcs.fetch_tmdb_poster_metadata()
        elif command == "6":
            interface_funcs.download_poster_images_local()
        elif command == "7":
            interface_funcs.fetch_watched_tmdb_metadata()
        elif command == "8":
            interface_funcs.diagnose_unresolved_watched_tmdb_metadata()
        elif command == "9":
            interface_funcs.ping_external_apis()
        ui.press_enter()


def open_candidate_pool_menu():
    """Открывает меню работы с общим пулом кандидатов."""
    while True:
        ui.clean_terminal()
        data, movies_counter = menu_state.get_menu_state()
        pool_stats_view = candidate_service.get_pool_stats_view()
        pool_stats_line = pool_stats_view["summary"]
        ui.show_candidate_pool_menu(movies_counter, pool_stats_line)

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 6)])
        if command == "0":
            return
        if command == "1":
            interface_funcs.run_tmdb_candidate_pool_flow()
        elif command == "2":
            interface_funcs.show_candidate_pool()
        elif command == "3":
            search_menu.show_global_candidate_search()
        elif command == "4":
            interface_funcs.mark_candidate_as_watched()
        elif command == "5":
            open_candidate_pool_management_menu()
        elif command == "6":
            open_candidate_pool_diagnostics_menu()

        ui.press_enter()

def open_candidate_pool_management_menu():
    """Открывает подменю управления общим pool."""
    while True:
        ui.clean_terminal()
        ui.show_candidate_pool_management_menu()

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 6)])
        if command == "0":
            return
        if command == "1":
            interface_funcs.delete_candidate_pool()
        elif command == "2":
            interface_funcs.edit_candidate_pool_filters()
        elif command == "3":
            interface_funcs.import_tmdb_result_to_common_pool_flow()
        elif command == "4":
            interface_funcs.collect_candidate_pool()
        elif command == "5":
            interface_funcs.clean_common_pool_duplicates()
        elif command == "6":
            interface_funcs.purge_pool_dataset_title_matches()

        ui.press_enter()


def open_candidate_pool_diagnostics_menu():
    """Открывает подменю диагностики и обслуживания пула."""
    while True:
        ui.clean_terminal()
        ui.show_candidate_pool_diagnostics_menu()

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 8)])
        if command == "0":
            return
        if command == "1":
            interface_funcs.show_suspicious_candidate_duplicates()
        elif command == "2":
            interface_funcs.retry_kp_for_incomplete_candidates()
        elif command == "3":
            interface_funcs.show_tmdb_dataset_genre_diagnostics()
        elif command == "4":
            interface_funcs.show_candidate_poster_diagnostics()
        elif command == "5":
            interface_funcs.download_candidate_pool_preview_posters()
        elif command == "6":
            interface_funcs.show_cross_year_candidate_duplicates()
        elif command == "7":
            interface_funcs.show_title_candidate_duplicates()

        ui.press_enter()


def open_tags_menu():
    """Открывает меню настройки тегов."""
    while True:
        ui.clean_terminal()
        ui.show_tags_menu()

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 4)])
        if command == "0":
            return
        if command == "1":
            tags_menu.show_tags()
        elif command == "2":
            tags_menu.request_new_tag()
        elif command == "3":
            tags_menu.request_delete_tag()
        elif command == "4":
            tags_menu.request_delete_all_tags()

        ui.press_enter()
