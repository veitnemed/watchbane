"""Prints console menu screens and terminal prompts."""

import os
import sys


MENU_WIDTH = 42


def clean_terminal():
    """Clear terminal when stdout is interactive."""
    if sys.stdout.isatty():
        os.system("cls")


def press_enter():
    """Wait for Enter before returning to a menu."""
    input("Enter, чтобы продолжить >>")


def show_menu_title(title: str):
    """Print centered submenu title."""
    print(f"\n{title.center(MENU_WIDTH)}\n")


def show_header(movies_counter: int, error: int):
    """Print common application header."""
    print("======= SERIES LIST =======")
    if movies_counter == 0:
        print("Список просмотренного пуст!\n")
    else:
        print(" " * 4, f"Просмотрено записей: {movies_counter}\n")


def show_global_menu(movies_counter: int, error: int = 0, candidate_summary=None):
    """Print main menu with maintenance as the primary path."""
    show_header(movies_counter, error)
    if isinstance(candidate_summary, dict):
        line = candidate_summary.get("line")
    else:
        line = candidate_summary
    if line not in (None, ""):
        print(f"{line}\n")
    print(" 1 >> Обслуживание")
    print(" 2 >> Просмотренное")
    print(" 3 >> Candidate pool")
    print(" 4 >> Поиск")
    print(" 5 >> Справочники")
    print(" 0 >> Выход\n")


def show_maintenance_menu(movies_counter: int, pool_stats_line: str, error: int = 0):
    """Print maintenance hub menu."""
    show_header(movies_counter, error)
    show_menu_title("ОБСЛУЖИВАНИЕ")
    print(f"{pool_stats_line}\n")
    print(" 1 >> Информациях о данных")
    print(" 2 >> Backup / restore")
    print(" 3 >> Metadata и poster-cache")
    print(" 4 >> Candidate pool cleanup")
    print(" 5 >> Диагностика API/cache")
    print(" 6 >> Проверки перед завершением рефакторинга")
    print(" 0 >> Главное меню\n")


def show_metadata_maintenance_menu():
    """Print metadata and poster-cache maintenance menu."""
    show_menu_title("METADATA И POSTER-CACHE")
    print(" 1 >> Обновить описания и poster-cache для просмотренных")
    print(" 2 >> Загрузить TMDb metadata для просмотренных")
    print(" 3 >> Загрузить poster URL из TMDb")
    print(" 4 >> Скачать poster images локально")
    print(" 5 >> Диагностика unresolved TMDb metadata")
    print(" 0 >> Назад\n")


def show_maintenance_diagnostics_menu():
    """Print read-only diagnostics menu."""
    show_menu_title("ДИАГНОСТИКА")
    print(" 1 >> Пинг API")
    print(" 2 >> Просмотр API признаков")
    print(" 3 >> Показать все жанры датасета")
    print(" 4 >> Показать TMDb жанры по dataset")
    print(" 5 >> Диагностика постеров в общем pool")
    print(" 0 >> Назад\n")


def show_watched_menu(movies_counter: int, error: int = 0):
    """Print watched dataset menu."""
    show_header(movies_counter, error)
    show_menu_title("ПРОСМОТРЕННОЕ")
    print(" 1 >> Показать просмотренное")
    print(" 2 >> Переименовать запись")
    print(" 3 >> Удалить просмотренную запись")
    print(" 4 >> Открыть Excel")
    print(" 5 >> Загрузить Excel")
    print(" 6 >> Добавить запись")
    print(" 0 >> Главное меню\n")


def show_data_menu(movies_counter: int, error: int = 0):
    """Compatibility screen for the old watched data menu."""
    show_watched_menu(movies_counter, error)


def show_candidate_pool_menu(movies_counter: int, pool_stats_line: str, error: int = 0):
    """Print candidate pool menu with generation moved into a submenu."""
    show_header(movies_counter, error)
    show_menu_title("CANDIDATE POOL")
    print(f"{pool_stats_line}\n")
    print(" 1 >> Посмотреть общий pool")
    print(" 2 >> Найти в pool")
    print(" 3 >> Отметить как просмотренное")
    print(" 4 >> Обслуживание pool")
    print(" 5 >> Импорт / сбор pool")
    print(" 0 >> Главное меню\n")


def show_candidate_pool_cleanup_menu():
    """Print candidate pool maintenance and diagnostics menu."""
    show_menu_title("ОБСЛУЖИВАНИЕ POOL")
    print(" 1 >> Статистика и просмотр pool")
    print(" 2 >> Очистить дубли в pool")
    print(" 3 >> Удалить из pool тайтлы из датасета")
    print(" 4 >> Показать подозрительные дубли")
    print(" 5 >> Cross-year: одно название, разный год")
    print(" 6 >> Дубли по названию")
    print(" 7 >> Диагностика постеров в общем pool")
    print(" 8 >> Запустить фоновую загрузку preview-постеров")
    print(" 9 >> Статус фоновой загрузки preview-постеров")
    print(" 10 >> Лог фоновой загрузки preview-постеров")
    print(" 11 >> Остановить фоновую загрузку preview-постеров")
    print(" 12 >> Скачать preview-постеры вручную")
    print(" 13 >> Диагностика metadata кандидатов")
    print(" 0 >> Назад\n")


def show_candidate_pool_import_menu():
    """Print rare candidate pool build/import menu."""
    show_menu_title("ИМПОРТ / СБОР POOL")
    print(" 1 >> Собрать TMDb pool")
    print(" 2 >> Импортировать TMDb result")
    print(" 3 >> Defaults фильтров поиска")
    print(" 0 >> Назад\n")


def show_candidate_pool_management_menu():
    """Compatibility screen for the old pool management menu."""
    show_candidate_pool_import_menu()


def show_candidate_pool_diagnostics_menu():
    """Compatibility screen for the old pool diagnostics menu."""
    show_candidate_pool_cleanup_menu()


def show_search_menu():
    """Print read-only search menu."""
    show_menu_title("ПОИСК")
    print(" 1 >> Поиск в candidate pool")
    print(" 2 >> Показать жанры датасета")
    print(" 3 >> Просмотр API признаков")
    print(" 0 >> Главное меню\n")


def show_reference_menu():
    """Print reference data menu."""
    show_menu_title("СПРАВОЧНИКИ")
    print(" 1 >> Жанры dataset")
    print(" 2 >> Теги")
    print(" 0 >> Главное меню\n")


def show_genres_menu():
    """Compatibility screen for the old genres menu."""
    show_menu_title("ЖАНРЫ")
    print(" 1 >> Показать жанровые поля dataset")
    print(" 0 >> Главное меню\n")


def show_extra_menu(movies_counter: int, error: int = 0):
    """Compatibility screen for the old extra menu."""
    show_maintenance_menu(movies_counter, "Candidate pool: см. раздел обслуживания", error)


def show_tags_menu():
    """Print tag settings menu."""
    show_menu_title("НАСТРОЙКА ТЕГОВ")
    print(" 1 >> Показать теги")
    print(" 2 >> Добавить тег")
    print(" 3 >> Удалить тег")
    print(" 4 >> Удалить все теги")
    print(" 0 >> Назад\n")
