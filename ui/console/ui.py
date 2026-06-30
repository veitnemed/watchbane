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
    print('======= SERIES LIST =======')
    if movies_counter == 0:
        print('Список просмотренного пуст!\n')
    else:
        print(' ' * 4, f'Просмотрено записей: {movies_counter}\n')


def show_global_menu(movies_counter: int, error: int = 0):
    """Печатает главное меню."""
    show_header(movies_counter, error)
    print(' 1 >> Просмотренное')
    print(' 2 >> Поиск сериалов')
    print(' 3 >> Жанры')
    print(' 4 >> Дополнительно')
    print(' 0 >> Выход\n')


def show_data_menu(movies_counter: int, error: int = 0):
    """Печатает меню данных."""
    show_header(movies_counter, error)
    show_menu_title('ПРОСМОТРЕННОЕ')
    print(' 1 >> Открыть Excel')
    print(' 2 >> Загрузить Excel')
    print(' 3 >> Добавить запись')
    print(' 4 >> Показать просмотренное')
    print(' 5 >> Данные о датасете')
    print(' 6 >> Бэкап')
    print(' 7 >> Переименовать запись')
    print(' 8 >> Удалить просмотренную запись')
    print(' 0 >> Главное меню\n')


def show_candidate_pool_menu(movies_counter: int, pool_stats_line: str, error: int = 0):
    """Печатает меню работы с общим пулом кандидатов."""
    show_header(movies_counter, error)
    show_menu_title('ПОИСК СЕРИАЛОВ')
    print(f'{pool_stats_line}\n')
    print(' 1 >> Обновить общий pool (TMDb)')
    print(' 2 >> Посмотреть общий pool')
    print(' 3 >> Найти сериалы в общем pool')
    print(' 4 >> Отметить просмотренные из pool')
    print(' 5 >> Управление pool')
    print(' 6 >> Диагностика и обслуживание')
    print(' 0 >> Главное меню\n')

def show_candidate_pool_management_menu():
    """Печатает подменю управления общим pool."""
    show_menu_title('УПРАВЛЕНИЕ POOL')
    print(' 1 >> Очистить общий pool')
    print(' 2 >> Defaults фильтров поиска')
    print(' 3 >> Импортировать TMDb result в общий pool')
    print(' 4 >> Собрать pool через KP API (legacy)')
    print(' 5 >> Очистить дубли в pool')
    print(' 6 >> Удалить из pool тайтлы из датасета')
    print(' 0 >> Назад\n')


def show_candidate_pool_diagnostics_menu():
    """Печатает подменю диагностики и обслуживания пула."""
    show_menu_title('ДИАГНОСТИКА И ОБСЛУЖИВАНИЕ')
    print(' 1 >> Показать подозрительные дубли')
    print(' 2 >> Добрать KP для неполных кандидатов')
    print(' 3 >> Показать TMDb жанры по dataset')
    print(' 4 >> Диагностика постеров в общем пуле')
    print(' 5 >> Скачать постеры candidate pool в preview-cache')
    print(' 6 >> Cross-year: одно название, разный год')
    print(' 7 >> Дубли по названию')
    print(' 0 >> Назад\n')


def show_genres_menu():
    """Печатает меню жанров."""
    show_menu_title('ЖАНРЫ')
    print(' 1 >> Показать жанровые поля dataset')
    print(' 0 >> Главное меню\n')


def show_extra_menu(movies_counter: int, error: int = 0):
    """Печатает дополнительное меню."""
    show_header(movies_counter, error)
    show_menu_title('ДОПОЛНИТЕЛЬНО')
    print(' 1 >> Просмотр API признаков')
    print(' 2 >> Показать все жанры датасета')
    print(' 3 >> Поиск в SQL по названию')
    print(' 4 >> Обновить описания и poster-cache для просмотренных')
    print(' 5 >> Загрузить poster URL из TMDb (metadata)')
    print(' 6 >> Скачать poster images локально')
    print(' 7 >> Загрузить TMDb metadata для просмотренных')
    print(' 8 >> Диагностика unresolved TMDb metadata')
    print(' 9 >> Пинг API')
    print(' 0 >> Главное меню\n')


def show_tags_menu():
    """Печатает меню тегов."""
    show_menu_title('НАСТРОЙКА ТЕГОВ')
    print(' 1 >> Показать теги')
    print(' 2 >> Добавить тег')
    print(' 3 >> Удалить тег')
    print(' 4 >> Удалить все теги')
    print(' 0 >> Назад\n')


