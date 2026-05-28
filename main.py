import time
import os
import constant
import format_score as format
import model
import request
import storage
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
        features[feature] = float(answer)

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

def train_model(data, weights, fit_func, title: str):
    start_time = time.perf_counter()

    print(title)
    old_error = model.mean_absolute_error(data, weights)
    new_weights = fit_func(data, weights)
    new_error = model.mean_absolute_error(data, new_weights)

    storage.save_weights(new_weights)
    end_time = time.perf_counter()
    delta_time = end_time - start_time

    ui.show_result_train(new_weights, old_error, new_error, delta_time)

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
        weights_without_feature = model.weights_without_feature(weights, feature)
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
        TRAIN_STEP = float(step)
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
            if storage.export_dataset_to_csv():
                storage.open_file(constant.EDIT_CSV)
        elif command == "2":
            storage.replace_dataset_from_edit_csv()
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
            funcs_list=[partial(valid.is_correct_select_menu,5)]
        )

        if command == "0":
            return
        elif command == "1":
            train_model(
                data,
                weights,
                lambda train_data, start_weights: model.fit_weights(train_data, start_weights, step=TRAIN_STEP),
                'Перебор весов 0..1'
            )
        elif command == "2":
            train_model(
                data,
                weights,
                lambda train_data, start_weights: model.fit_weights_until_plateau(
                    train_data,
                    start_weights,
                    score=TRAIN_PLATEAU_SCORE,
                    step=TRAIN_STEP
                ),
                'Рандомное обучение'
            )
        elif command == "3":
            length = len(data)
            model.one_to_one_error(data, min(10, length))
        elif command == "4":
            get_predict(weights)
        elif command == "5":
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

        press_enter()

def main_loop():
    storage.init_meta()
    storage.init_dataset()
    storage.init_weights()
    storage.init_txt()
    storage.init_csv()
    storage.create_backup()

    while True:
        ui.clean_terminal()
        data, weights, movies_counter, abs_error = get_menu_state()
        ui.show_main_menu(movies_counter, round(abs_error, 2))

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
