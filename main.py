import time
import os
import constant
import excel_work
import format_score as format
import model
import request
import storage
import tags_work
import ui
import valid
from functools import partial


TRAIN_STEP = constant.STEP
TRAIN_PLATEAU_SCORE = 20

def press_enter():
    input('Enter, чтобы продолжить >>')

def show_all_movies():
    data = storage.load_dataset()
    if len(data) == 0:
        print('Датасет пуст!')
        return

    for idx, movie in enumerate(data.values()):
        main_info = movie["main_info"]
        print(f"{idx + 1}) {main_info['title']} | оценка: {main_info['user_score']}")

def get_predict(weights: dict) -> None:
    title = request.loop_input(text='Введите название: ',funcs_list=[valid.is_correct_title])

    features = {}
    for feature in constant.FEATURES:
        answer = request.loop_input(
            text=f'{feature} >> ',
            funcs_list=[valid.is_correct_score]
        )
        features[feature] = valid.parse_float(answer)

    score = model.predict_score(features, weights)
    print(f'Оценка модели для {title}: {score}')

def request_object() -> None:
    ui.clean_terminal()

    movie_request = request.request_all_scores()
    result = storage.add_movie(movie_request)

    if result:
        print('Новая запись добавлена!')
    else:
        print('Ошибка! Новая запись не добавлена')

def train_model(data, weights, fit_func, title: str, **train_kwargss):
    start_time = time.perf_counter()

    print(title)
    old_error = model.mean_absolute_error(data, weights)
    new_weights = fit_func(data, weights, **train_kwargss)
    new_error = model.mean_absolute_error(data, new_weights)

    if new_error <= old_error:
        storage.save_weights(new_weights)
    else:
        new_weights = weights
        new_error = old_error
        print('Новые веса не сохранены: ошибка модели увеличилась.')
    end_time = time.perf_counter()
    delta_time = end_time - start_time

    ui.show_result_train(new_weights, old_error, new_error, delta_time)


def auto_train_grid_steps(data, weights, title: str):
    start_time = time.perf_counter()
    step_values = constant.STEPS_TRAIN
    error_now = model.mean_absolute_error(data, weights)
    best_weights = weights.copy()
    best_error = error_now

    print(title)
    for step in step_values:
        new_weights = model.fit_weights(data,best_weights,passes=5, step = step)
        new_error = model.mean_absolute_error(data,new_weights)

        if new_error < best_error:
            best_error = new_error
            best_weights = new_weights

        print(f'step: {step} | error_now: {round(best_error,2)}')
    storage.save_weights(best_weights)
    end_time = time.perf_counter()
    delta_time = end_time - start_time
    ui.show_result_train(best_weights, error_now, best_error, delta_time)

def auto_train_mix_mode(data, weights, title: str):
    start_time = time.perf_counter()
    step_values = constant.STEPS_TRAIN_MIX
    error_now = model.mean_absolute_error(data, weights)
    best_weights = weights.copy()
    best_error = error_now

    print(title)
    for step in step_values:
        
        no_mut = 0
        while True:
            new_weights_1 = model.fit_weights(data,best_weights,passes=1, step = step)
            new_error_1 = model.mean_absolute_error(data,new_weights_1)
            if new_error_1 < best_error:
                best_error = new_error_1
                best_weights = new_weights_1
                no_mut = 0
            else:
                no_mut +=1
        
            new_weights_2 = model.fit_weights_until_plateau(data = data,start_weights = best_weights,score = 200, step = step)
            new_error_2 = model.mean_absolute_error(data,new_weights_2)
        
            if new_error_2 < best_error:
                best_error = new_error_2
                best_weights = new_weights_2
                no_mut = 0
            else:
                no_mut +=1
                
            if no_mut >= 5:
                break
            
        print(f'step: {step} | error_now: {round(best_error,2)}')
    storage.save_weights(best_weights)
    end_time = time.perf_counter()
    delta_time = end_time - start_time
    ui.show_result_train(best_weights, error_now, best_error, delta_time)

def show_mean_error(data, weights):
    ui.clean_terminal()
    abs_error = model.mean_absolute_error(data, weights)
    error = model.mean_error(data, weights)
    print(f'\nСредняя ошибка модели: {round(abs_error, 2)}')
    print(f'\nСреднее линейное отклонение: {round(error, 2)}')

def show_weights_model(weights):
    ui.clean_terminal()
    print('Веса модели:\n')
    for weight, value in weights.items():
        print(f'{weight}: {round(value, 2)}')

def reset_weights_model():
    storage.save_weights(constant.DEFAULT_WEIGHTS.copy())
    print('Веса сброшены на значения по умолчанию.')

def votes_impact():
    data = storage.load_meta()
    for title, obj in data.items():
        raw_scores = obj.get("raw_scores", obj.get("raw"))
        main_info = obj.get("main_info", {})
        year = main_info.get("year", raw_scores.get("year"))
        kp_votes, imdb_votes = raw_scores["kp_votes"], raw_scores["imdb_votes"]
        kp = format.popularity_kp(kp_votes, year)
        imdb = format.popularity_score(imdb_votes, year)
        print(f'{title} ({year})\n')
        print(f'KP: {kp_votes} -> {round(kp, 1)}')
        print(f'IMDB: {imdb_votes} -> {round(imdb, 1)}\n')


def show_feature_importance(weights, full_error):
    ui.clean_terminal()
    data = storage.load_dataset()
    for feature in constant.FEATURES:
        weights_without_feature = model.selection_weights_without_feature(data, feature, weights)
        error_without_feature = model.mean_absolute_error(data, weights_without_feature)
        eps = error_without_feature - full_error
        print(f"Ошибка без {feature}: {round(error_without_feature * 10, 1)} %")
        print(f"Эффективность: {round(eps, 2)} \n")

def get_menu_state():
    data = storage.load_dataset()
    weights = storage.load_weights()
    movies_counter = len(data)
    abs_error = model.mean_absolute_error(data, weights)
    return data, weights, movies_counter, abs_error

def setup_train_params():
    global TRAIN_STEP, TRAIN_PLATEAU_SCORE

    step = request.loop_input(
        text=f'Шаг обучения [{TRAIN_STEP}] >> ',
        funcs_list=[valid.is_correct_train_step]
    )
    plateau_score = request.loop_input(
        text=f'Попыток без улучшения для плато [{TRAIN_PLATEAU_SCORE}] >> ',
        funcs_list=[valid.is_correct_plateau_score]
    )

    if step.strip() != "":
        TRAIN_STEP = valid.parse_float(step)
    if plateau_score.strip() != "":
        TRAIN_PLATEAU_SCORE = int(plateau_score)
    print(f'Параметры обучения обновлены: шаг={TRAIN_STEP}, плато={TRAIN_PLATEAU_SCORE}')



def open_data_menu():
    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = get_menu_state()
        ui.show_data_menu(movies_counter, round(abs_error, 2))

        command = request.loop_input(text=">> ",funcs_list=[partial(valid.is_correct_select_menu,4)])
        if command == "0":
            return
        elif command == "1":
            if excel_work.export_dataset_to_excel():
                storage.open_file(constant.EDIT_EXCEL)
        elif command == "2":
            excel_work.replace_dataset_from_excel()
        elif command == "3":
            request_object()
        elif command == "4":
            show_all_movies()

        # Временно скрыто из меню:
        # storage.input_csv()
        # storage.clean_dataset()

        press_enter()

def open_train_menu():
    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = get_menu_state()
        ui.show_train_menu(movies_counter, round(abs_error, 2), TRAIN_STEP, TRAIN_PLATEAU_SCORE)

        command = request.loop_input(
            text=">> ",
            funcs_list=[partial(valid.is_correct_select_menu,7)]
        )

        if command == "0":
            return
        elif command == "1":
            train_model(
                data = data,
                weights = weights,
                fit_func = model.fit_weights,
                title = 'Перебор весов 0..1',
                step = TRAIN_STEP
            )
        elif command == "2":
            train_model(
                data = data,
                weights = weights,
                fit_func = model.fit_weights_until_plateau,
                title = 'Рандомное обучение',
                step = TRAIN_STEP,
                score = TRAIN_PLATEAU_SCORE
            )
        elif command == "3":
            auto_train_grid_steps(data = data,
                                  weights = weights,
                                  title= 'Перебор по шагам')
        elif command == "4":
            auto_train_mix_mode(data = data,
                                weights = weights,
                                title= 'Усиленное обучение')
        elif command == "5":
            length = len(data)
            model.one_to_one_error(data, min(10, length))
        elif command == "6":
            get_predict(weights)
        elif command == "7":
            setup_train_params()
        


        press_enter()

def open_weights_menu():
    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = get_menu_state()
        ui.show_weights_menu(movies_counter, round(abs_error, 2))

        command = request.loop_input(
            text=">> ",
            funcs_list=[partial(valid.is_correct_select_menu,3)]
        )

        if command == "0":
            return
        elif command == "1":
            show_weights_model(weights)
        elif command == "2":
            show_feature_importance(weights, abs_error)
        elif command == "3":
            reset_weights_model()

        press_enter()

def open_extra_menu():
    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = get_menu_state()
        ui.show_extra_menu(movies_counter, round(abs_error, 2))

        command = request.loop_input(
            text=">> ",
            funcs_list=[partial(valid.is_correct_select_menu,3)]
        )

        if command == "0":
            return
        elif command == "1":
            votes_impact()
        elif command == "2":
            updated_count = storage.rework_formated_scores()
            print(f'Пересчитано записей: {updated_count}')
        elif command == "3":
            open_tags_menu()

        press_enter()


def open_tags_menu():
    while True:
        ui.clean_terminal()
        ui.show_tags_menu()

        command = request.loop_input(
            text=">> ",
            funcs_list=[partial(valid.is_correct_select_menu, 3)]
        )

        if command == "0":
            return
        elif command == "1":
            tags_work.show_tags()
        elif command == "2":
            tags_work.request_new_tag()
        elif command == "3":
            tags_work.request_delete_tag()

        press_enter()


def main_loop():

    storage.init_all_dates()

    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = get_menu_state()
        kp_error = model.kp_mean_absolute_error(data)
        ui.show_main_menu(movies_counter, round(abs_error, 2), kp_error)

        command = request.loop_input(text=">> ",funcs_list=[partial(valid.is_correct_select_menu, 4)])
        if command == "0":
            break
        elif command == "1":
            open_data_menu()
        elif command == "2":
            open_train_menu()
        elif command == "3":
            open_weights_menu()
        elif command == "4":
            open_extra_menu()


if __name__ == "__main__":
    main_loop()
