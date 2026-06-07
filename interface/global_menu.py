"""Содержит циклы главного меню и подменю приложения."""

from functools import partial

from config import constant
from config import tags_work
from data_work import excel_work
from data_work import storage
from interface import global_menu_funcs
from interface import interface_funcs
from interface import request
from interface import ui
from model_work import model
from model_work import train_modes
from core import valid


def open_data_menu():
    """Открывает меню работы с данными."""
    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = global_menu_funcs.get_menu_state()
        ui.show_data_menu(movies_counter, round(abs_error, 2))

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 5)])
        if command == "0":
            return
        elif command == "1":
            if excel_work.export_dataset_to_excel():
                storage.open_file(constant.EDIT_EXCEL)
        elif command == "2":
            excel_work.replace_dataset_from_excel()
        elif command == "3":
            interface_funcs.request_object()
        elif command == "4":
            interface_funcs.show_all_movies()
        elif command == "5":
            interface_funcs.show_data_info()

        global_menu_funcs.press_enter()


def open_train_menu():
    """Открывает меню обучения модели."""
    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = global_menu_funcs.get_menu_state()
        ui.show_train_menu(
            movies_counter,
            round(abs_error, 2),
            global_menu_funcs.TRAIN_STEP,
            global_menu_funcs.TRAIN_PLATEAU_SCORE
        )

        command = request.loop_input(
            text=">> ",
            funcs_list=[partial(valid.is_correct_select_menu, 8)]
        )

        if command == "0":
            return
        elif command == "1":
            train_modes.train_model(
                data=data,
                weights=weights,
                fit_func=model.fit_weights,
                title='Перебор весов 0..1',
                step=global_menu_funcs.TRAIN_STEP
            )
        elif command == "2":
            train_modes.train_model(
                data=data,
                weights=weights,
                fit_func=model.fit_weights_until_plateau,
                title='Рандомное обучение',
                step=global_menu_funcs.TRAIN_STEP,
                score=global_menu_funcs.TRAIN_PLATEAU_SCORE
            )
        elif command == "3":
            train_modes.auto_train_grid_steps(
                data=data,
                weights=weights,
                title='Перебор по шагам'
            )
        elif command == "4":
            train_modes.auto_train_mix_mode(
                data=data,
                weights=weights,
                title='Усиленное обучение'
            )
        elif command == "5":
            length = len(data)
            model.one_to_one_error(data, min(10, length))
        elif command == "6":
            interface_funcs.get_predict(weights)
        elif command == "7":
            global_menu_funcs.setup_train_params()
        elif command == "8":
            global_menu_funcs.export_train_report()

        global_menu_funcs.press_enter()


def open_weights_menu():
    """Открывает меню просмотра и сброса весов."""
    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = global_menu_funcs.get_menu_state()
        ui.show_weights_menu(movies_counter, round(abs_error, 2))

        command = request.loop_input(
            text=">> ",
            funcs_list=[partial(valid.is_correct_select_menu, 3)]
        )

        if command == "0":
            return
        elif command == "1":
            interface_funcs.show_weights_model(weights)
        elif command == "2":
            interface_funcs.show_feature_importance(weights, abs_error)
        elif command == "3":
            interface_funcs.reset_weights_model()

        global_menu_funcs.press_enter()


def open_extra_menu():
    """Открывает меню дополнительных действий."""
    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = global_menu_funcs.get_menu_state()
        ui.show_extra_menu(movies_counter, round(abs_error, 2))

        command = request.loop_input(
            text=">> ",
            funcs_list=[partial(valid.is_correct_select_menu, 2)]
        )

        if command == "0":
            return
        elif command == "1":
            interface_funcs.votes_impact()
        elif command == "2":
            updated_count = storage.rework_formated_scores()
            print(f'Пересчитано записей: {updated_count}')

        global_menu_funcs.press_enter()


def open_tags_menu():
    """Открывает меню настройки тегов."""
    while True:
        ui.clean_terminal()
        ui.show_tags_menu()

        command = request.loop_input(
            text=">> ",
            funcs_list=[partial(valid.is_correct_select_menu, 4)]
        )

        if command == "0":
            return
        elif command == "1":
            tags_work.show_tags()
        elif command == "2":
            tags_work.request_new_tag()
        elif command == "3":
            tags_work.request_delete_tag()
        elif command == "4":
            tags_work.request_delete_all_tags()

        global_menu_funcs.press_enter()
