"""LEGACY: устаревший скрипт на старом плоском layout (patterns/storage/valid).

Не импортируется текущим меню и несовместим с актуальной структурой пакетов
(common/config/storage/dataset/candidates/model/apis/ui). Оставлен как есть до
отдельного решения: удалить или переписать под новые модули.
"""

import csv
import random
import time

import patterns
import storage
import ui
import valid


MIN_COMPLETED_SERIES = 5


def get_sorted_list(
    series: storage.CsvRows,
    rounds: int,
) -> tuple[storage.CsvRows, dict[str, float], int]:
    """Провести сравнения и переставить оценки выбранных сериалов."""

    length = len(series)
    comparisons = min(rounds, length - 1)
    available_indexes = list(range(length - 1))
    changed_count = 0

    for step in range(comparisons):
        distance = random.randint(1, 2)
        valid_indexes = [index for index in available_indexes if index + distance < length]
        if not valid_indexes:
            distance = 1
            valid_indexes = available_indexes
        index = random.choice(valid_indexes)
        available_indexes.remove(index)

        first_name = series[index][1]
        second_name = series[index + distance][1]
        reverse_order = random.randint(1, 2) == 2

        ui.clean_terminal()
        print(f"Раунд {step + 1}/{comparisons}:\n")
        print("Какой сериал нравится больше?\n")

        if reverse_order:
            print(f"1. {second_name}")
            print(f"2. {first_name}")
        else:
            print(f"1. {first_name}")
            print(f"2. {second_name}")

        while True:
            answer = input(">> ").strip()
            if valid.is_valid_mode(answer, 2):
                break
            print("Некорректный ввод")

        lower_ranked_selected = answer == ("1" if reverse_order else "2")
        if lower_ranked_selected:
            series[index][2], series[index + distance][2] = (
                series[index + distance][2],
                series[index][2],
            )
            changed_count += 1

    current_grades = {row[0]: float(row[2].replace(",", ".")) for row in series}
    return series, current_grades, changed_count


def show_now_top(
    series: storage.CsvRows,
    current_grades: dict[str, float],
    old_grades: dict[str, float],
    changed_count: int,
) -> None:
    """Показать сериалы, оценки которых изменились после сравнений."""

    id_to_name = {row[0]: row[1] for row in series}
    current_top = sorted(current_grades.items(), key=lambda item: item[1], reverse=True)
    max_name_length = max(len(id_to_name[series_id]) for series_id, _ in current_top)

    print("-" * 20, "БЫЛО -> СТАЛО", "-" * 20)
    printed_count = 0
    for series_id, new_grade in current_top:
        old_grade = old_grades.get(series_id, new_grade)
        if old_grade == new_grade:
            continue
        name = id_to_name[series_id]
        printed_count += 1
        print(f"{printed_count:>2}) {name:<{max_name_length}}  {old_grade:g} -> {new_grade:g}  [ID: {series_id}]")

    if printed_count == 0:
        print("\nНи один из сериалов не поменял оценку!\n")
    else:
        print(f"\nКоличество сравнений с перестановкой оценок: {changed_count}\n")


def create_file(completed: storage.CsvRows, rest: storage.CsvRows) -> None:
    """Сохранить результаты сравнения в рабочий CSV."""

    with open(storage.NAME_FILE, "w", encoding=storage.CSV_ENCODING, newline="") as file:
        writer = csv.writer(file, delimiter=storage.CSV_DELIMITER)
        writer.writerow(storage.CSV_COLUMNS)
        writer.writerows(completed)
        writer.writerows(rest)


def ask_amount_rounds(amount_series: int) -> int:
    """Запросить количество сравнений без повторения базовых индексов."""

    max_rounds = amount_series - 1
    print("Режим сравнения сериалов!\n")
    while True:
        print(f"Введите количество сравнений (не больше {max_rounds}):")
        try:
            rounds = int(input(">> ").strip())
        except ValueError:
            print("Некорректный ввод")
            continue
        if 1 <= rounds <= max_rounds:
            return rounds
        print(f"Значение должно быть от 1 до {max_rounds} включительно!")


def start_comparison() -> bool:
    """Запустить интерактивный режим уточнения рейтинга."""

    if not valid.is_minimal_completed(MIN_COMPLETED_SERIES):
        print(f"Для данного режима необходимо минимум {MIN_COMPLETED_SERIES} просмотренных сериалов!")
        time.sleep(2)
        return True

    all_series = storage.created_list_csv()[1:]
    completed = [row for row in all_series if row[4] == "completed"]
    old_grades = {row[0]: float(row[2].replace(",", ".")) for row in completed}

    storage.sorted_grade()
    all_series = storage.created_list_csv()[1:]
    completed = [row for row in all_series if row[4] == "completed"]
    rest = [row for row in all_series if row[4] != "completed"]

    rounds = ask_amount_rounds(len(completed))
    sorted_list, current_grades, changed_count = get_sorted_list(completed, rounds)
    show_now_top(sorted_list, current_grades, old_grades, changed_count)

    create_file(sorted_list, rest)
    storage.sorted_grade()
    return patterns.pattern_back_main()
