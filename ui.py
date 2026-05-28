import os


def clean_terminal():
    os.system('cls')


def show_header(movies_counter: int, error: int):
    print('======= TERMINAL MOVIES LEARN =======')
    if movies_counter == 0:
        print('Датасет пуст!\n')
    else:
        print(' ' * 7, f'Количество записей: {movies_counter}')
    print(' ' * 12, f"MAE: {round(error * 10, 2)} %\n")


def show_main_menu(movies_counter: int, error: int):
    show_header(movies_counter, error)
    print(' 1 >> Данные')
    print(' 2 >> Обучение')
    print(' 3 >> Веса')
    print(' 4 >> Дополнительно')
    print(' 0 >> Выход\n')


def show_data_menu(movies_counter: int, error: int):
    show_header(movies_counter, error)
    print('ДАННЫЕ')
    print(' 1 >> Открыть датасет')
    print(' 2 >> Загрузить датасет')
    print(' 3 >> Добавить запись')
    print(' 4 >> Показать мои оценки')
    print(' 0 >> Главное меню\n')


def show_train_menu(movies_counter: int, error: int, step: float, plateau_score: int):
    show_header(movies_counter, error)
    print('ОБУЧЕНИЕ')
    print(f'Шаг: {step} | Плато: {plateau_score} попыток без улучшения\n')
    print(' 1 >> Перебор весов 0..1')
    print(' 2 >> Рандомное обучение')
    print(' 3 >> Прогноз для каждого объекта')
    print(' 4 >> Сделать прогноз')
    print(' 5 >> Параметры обучения')
    print(' 0 >> Главное меню\n')


def show_weights_menu(movies_counter: int, error: int):
    show_header(movies_counter, error)
    print('ВЕСА')
    print(' 1 >> Показать веса')
    print(' 2 >> Расчет влияния каждого параметра')
    print(' 3 >> Сбросить веса')
    print(' 0 >> Главное меню\n')


def show_extra_menu(movies_counter: int, error: int):
    show_header(movies_counter, error)
    print('ДОПОЛНИТЕЛЬНО')
    print(' 1 >> Показать влияние количества голосов')
    print(' 2 >> Пересчитать raw оценки')
    print(' 0 >> Главное меню\n')


def show_result_train(new_weights: dict, old_error: float, new_error: float, delta_time: float):
    print('=' * 50)
    print('Новые веса:\n')
    for weight, value in new_weights.items():
        print(f'{weight}: {round(value, 4)}')

    print('\nОшибка до обучения:', round(old_error, 4))
    print('Ошибка после обучения:', round(new_error, 4))
    print(f'\nВремя подбора весов: {round(delta_time, 4)} сек.\n')
    print('=' * 50)
