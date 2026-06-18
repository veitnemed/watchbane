"""Главный файл приложения: запускает терминальное меню."""

from functools import partial

from common import valid
from data_work import storage
from ui import global_menu
from ui import menu_state
from ui import request
from ui import ui
from model import model

def main_loop():
    """Запускает главный цикл программы."""
    storage.init_all_dates()

    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = menu_state.get_menu_state()
        kp_error = model.kp_mean_absolute_error(data)
        loo_mae = storage.get_saved_loo_mae()
        ui.show_global_menu(movies_counter, round(abs_error, 2), kp_error, loo_mae)

        command = request.loop_input(text=">> ", funcs_list=[partial(valid.is_correct_select_menu, 6)])
        if command == "0":
            break
        elif command == "1":
            global_menu.open_data_menu()
        elif command == "2":
            global_menu.open_train_menu()
        elif command == "3":
            global_menu.open_model_menu()
        elif command == "4":
            global_menu.open_extra_menu()
        elif command == "5":
            global_menu.open_candidate_pool_menu()
        elif command == "6":
            global_menu.export_report()
            ui.press_enter()

if __name__ == "__main__":
    main_loop()
