"""Печатает экраны, заголовки и пункты терминального меню."""

import os


MENU_WIDTH = 38


def clean_terminal():
    """Очищает терминал."""
    os.system('cls')


def show_menu_title(title: str):
    """Печатает центрированный заголовок подменю."""
    print(f'\n{title.center(MENU_WIDTH)}\n')


def show_header(movies_counter: int, error: int):
    """Печатает общий заголовок приложения."""
    print('======= TERMINAL MOVIES LEARN =======')
    if movies_counter == 0:
        print('Датасет пуст!\n')
    else:
        print(' ' * 7, f'Количество записей: {movies_counter}')
    print(' ' * 12, f"MAE: {round(error * 10, 2)} %\n")


def show_global_menu(movies_counter: int, error: int, kp_error: int):
    """Печатает главное меню."""
    show_header(movies_counter, error)
    print(' ' * 9, f"KP_MAE: {round(kp_error * 10, 2)} %\n")
    print(' 1 >> Данные')
    print(' 2 >> Обучение')
    print(' 3 >> Веса')
    print(' 4 >> Настройка тегов')
    print(' 5 >> Дополнительно')
    print(' 0 >> Выход\n')


def show_data_menu(movies_counter: int, error: int):
    """Печатает меню данных."""
    show_header(movies_counter, error)
    show_menu_title('ДАННЫЕ')
    print(' 1 >> Открыть датасет в Excel')
    print(' 2 >> Загрузить датасет из Excel')
    print(' 3 >> Добавить запись')
    print(' 4 >> Показать мои оценки')
    print(' 5 >> Данные о датасете')
    print(' 0 >> Главное меню\n')


def show_train_menu(movies_counter: int, error: int, step: float, plateau_score: int):
    """Печатает меню обучения."""
    show_header(movies_counter, error)
    show_menu_title('ОБУЧЕНИЕ')
    print(f'Шаг: {step} | Плато: {plateau_score} попыток без улучшения\n')
    print(' 1 >> Координатный поиск')
    print(' 2 >> Случайная оптимизация')
    print(' 3 >> Многошаговый координатный поиск')
    print(' 4 >> Гибридная оптимизация\n')
    print(' 5 >> Leave-one-out проверка')
    print(' 6 >> Сделать прогноз')
    print(' 7 >> Параметры обучения')
    print(' 8 >> Выгрузить отчет\n')
    print(' 0 >> Главное меню\n')


def show_weights_menu(movies_counter: int, error: int):
    """Печатает меню весов."""
    show_header(movies_counter, error)
    show_menu_title('ВЕСА')
    print(' 1 >> Показать веса модели')
    print(' 2 >> Расчет влияния каждого параметра')
    print(' 3 >> Сбросить веса модели\n')
    print(' 0 >> Главное меню\n')


def show_extra_menu(movies_counter: int, error: int):
    """Печатает дополнительное меню."""
    show_header(movies_counter, error)
    show_menu_title('ДОПОЛНИТЕЛЬНО')
    print(' 1 >> Показать влияние количества голосов')
    print(' 2 >> Пересчитать raw оценки')
    print(' 0 >> Главное меню\n')


def show_tags_menu():
    """Печатает меню тегов."""
    show_menu_title('НАСТРОЙКА ТЕГОВ')
    print(' 1 >> Показать теги')
    print(' 2 >> Добавить тег')
    print(' 3 >> Удалить тег')
    print(' 4 >> Удалить все теги')
    print(' 0 >> Назад\n')


def show_result_train(new_weights: dict, old_error: float, new_error: float, delta_time: float):
    """Печатает результат обучения модели."""
    print('=' * 50)
    print('Новые веса:\n')
    for weight, value in new_weights.items():
        print(f'{weight}: {round(value, 4)}')

    print('\nОшибка до обучения:', round(old_error, 4))
    print('Ошибка после обучения:', round(new_error, 4))
    print(f'\nВремя подбора весов: {round(delta_time, 4)} сек.\n')
    print('=' * 50)
