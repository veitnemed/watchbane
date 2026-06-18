"""Печатает экраны, заголовки и пункты терминального меню."""

import os
import sys


MENU_WIDTH = 38


def clean_terminal():
    """Очищает терминал."""
    if sys.stdout.isatty():
        os.system('cls')


def press_enter():
    """Ждет нажатия Enter."""
    input('Enter, чтобы продолжить >>')


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


def show_global_menu(movies_counter: int, error: int, kp_error: int, loo_mae=None):
    """Печатает главное меню."""
    show_header(movies_counter, error)
    print(' ' * 9, f"KP_MAE: {round(kp_error * 10, 2)} %\n")
    if loo_mae is None:
        print(' ' * 8, "LOO MAE: не рассчитан\n")
    else:
        print(' ' * 8, f"LOO MAE: {float(loo_mae):.4f}\n")
    print(' 1 >> Данные')
    print(' 2 >> Обучение')
    print(' 3 >> Модель')
    print(' 4 >> Дополнительно')
    print(' 5 >> Пулл кандидатов')
    print(' 6 >> Выгрузить отчёт')
    print(' 0 >> Выход\n')


def show_data_menu(movies_counter: int, error: int):
    """Печатает меню данных."""
    show_header(movies_counter, error)
    show_menu_title('ДАННЫЕ')
    print(' 1 >> Открыть Excel')
    print(' 2 >> Загрузить Excel')
    print(' 3 >> Добавить запись')
    print(' 4 >> Показать мои оценки')
    print(' 5 >> Данные о датасете')
    print(' 6 >> Бэкап')
    print(' 7 >> Переименовать запись')
    print(' 0 >> Главное меню\n')


def show_candidate_pool_menu(movies_counter: int, error: int, candidates_count: int):
    """Печатает меню работы с общим пулом кандидатов."""
    show_header(movies_counter, error)
    show_menu_title('ПУЛЛ КАНДИДАТОВ')
    print(f'Всего кандидатов: {candidates_count}\n')
    print(' 1 >> Собрать новый пулл')
    print(' 2 >> Посмотреть пуллы кандидатов')
    print(' 3 >> Собрать топ из общего пула')
    print(' 4 >> Отметить просмотренные из пулла')
    print(' 5 >> Управление пуллами')
    print(' 6 >> Диагностика и обслуживание')
    print(' 0 >> Главное меню\n')


def show_candidate_pool_collect_menu():
    """Печатает подменю сборки нового пула кандидатов."""
    show_menu_title('СОБРАТЬ НОВЫЙ ПУЛЛ')
    print(' 1 >> TMDb -> IMDb SQL -> KP API')
    print(' 2 >> Legacy IMDb SQL -> KP API')
    print(' 3 >> TMDb test-run')
    print(' 0 >> Назад\n')


def show_candidate_pool_management_menu():
    """Печатает подменю управления сохранёнными пулами."""
    show_menu_title('УПРАВЛЕНИЕ ПУЛЛАМИ')
    print(' 1 >> Удалить пулл')
    print(' 2 >> Фильтрация / редактирование критериев')
    print(' 3 >> Импортировать TMDb result в общий пул')
    print(' 0 >> Назад\n')


def show_candidate_pool_diagnostics_menu():
    """Печатает подменю диагностики и обслуживания пула."""
    show_menu_title('ДИАГНОСТИКА И ОБСЛУЖИВАНИЕ')
    print(' 1 >> Показать подозрительные дубли')
    print(' 2 >> Добрать KP для неполных кандидатов')
    print(' 3 >> Показать вклады для кандидатов')
    print(' 0 >> Назад\n')


def show_train_menu(movies_counter: int, error: int):
    """Печатает меню обучения."""
    show_header(movies_counter, error)
    show_menu_title('ОБУЧЕНИЕ')
    print(' 1 >> Линейная регрессия')
    print(' 2 >> Попарное сравнение оценок')
    print(' 3 >> Проверка устойчивости к шуму')
    print(' 4 >> LOO обучение')
    print(' 0 >> Главное меню\n')


def show_model_menu(movies_counter: int, error: int):
    """Печатает меню модели."""
    show_header(movies_counter, error)
    show_menu_title('МОДЕЛЬ')
    print(' 1 >> Признаки')
    print(' 2 >> Тесты эффективности')
    print(' 3 >> Сделать прогноз\n')
    print(' 0 >> Главное меню\n')


def show_feature_menu():
    """Печатает меню признаков."""
    show_menu_title('ПРИЗНАКИ')
    print(' 1 >> Вайб-тэги')
    print(' 2 >> Жанровая разметка')
    print(' 3 >> Показать веса модели')
    print(' 4 >> Сбросить веса модели')
    print(' 0 >> Назад\n')


def show_efficiency_menu(movies_counter: int, error: int):
    """Печатает меню тестов эффективности."""
    show_header(movies_counter, error)
    show_menu_title('ТЕСТЫ ЭФФЕКТИВНОСТИ')
    print(' 1 >> Оценить вклады')
    print(' 2 >> Рассчитать ошибку для топ N')
    print(' 3 >> Leave-one-out проверка')
    print(' 4 >> Проверка устойчивости к шуму')
    print(' 5 >> Показать влияние голосов')
    print(' 6 >> Пересчитать raw оценки')
    print(' 0 >> Назад\n')


def show_extra_menu(movies_counter: int, error: int):
    """Печатает дополнительное меню."""
    show_header(movies_counter, error)
    show_menu_title('ДОПОЛНИТЕЛЬНО')
    print(' 1 >> Просмотр API признаков')
    print(' 2 >> Показать все жанры датасета')
    print(' 3 >> Показать влияние голосов')
    print(' 4 >> Пересчитать raw оценки')
    print(' 5 >> Поиск в SQL по названию')
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
