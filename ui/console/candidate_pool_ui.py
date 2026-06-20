"""Интерактивный ввод для работы с пулом кандидатов."""

from datetime import datetime

from config import constant
from common import valid
from candidates import candidate_pool


def format_optional_default(value) -> str:
    """Возвращает подпись значения по умолчанию для необязательного фильтра."""
    if value in (None, ""):
        return "не важно"
    if isinstance(value, list):
        return ", ".join(value) if len(value) > 0 else "не важно"
    return str(value)


def prompt_optional_int(label: str, default=None, min_value: int = 0) -> int | None:
    """Запрашивает необязательное целое число."""
    while True:
        suffix = f" [{format_optional_default(default)}]"
        answer = input(f"{label}{suffix} >> ").strip()
        if answer == "":
            return default
        if valid.is_correct_votes(answer) is False:
            print("Введите целое число 0 или больше.")
            continue
        value = int(answer)
        if value < min_value:
            print(f"Введите число не меньше {min_value}.")
            continue
        return value


def prompt_optional_year(label: str, default=None) -> int | None:
    """Запрашивает необязательный год."""
    while True:
        suffix = f" [{format_optional_default(default)}]"
        answer = input(f"{label}{suffix} >> ").strip()
        if answer == "":
            return default
        if valid.is_correct_year(answer) is False:
            print(f"Введите год в диапазоне 2000-{constant.NOW_YEAR}.")
            continue
        return int(answer)


def prompt_optional_score(label: str, default=None) -> float | None:
    """Запрашивает необязательную оценку."""
    while True:
        suffix = f" [{format_optional_default(default)}]"
        answer = input(f"{label}{suffix} >> ").strip()
        if answer == "":
            return default
        if valid.is_correct_score(answer) is False:
            print("Введите число от 0 до 10.")
            continue
        return valid.parse_float(answer)


def choose_genres_by_numbers(
    current_genres: list | None = None,
    prompt_title: str = "Выберите жанры по номерам через пробел.",
    prompt_hint: str = "Можно оставить пусто, тогда фильтра по жанрам не будет.",
    input_label: str = "Номера жанров",
) -> list:
    """Дает выбрать жанры по номерам из списка."""
    if current_genres is None:
        current_genres = []

    genres = candidate_pool.get_available_genres()
    if len(genres) == 0:
        print("Список жанров пока пуст.")
        return current_genres

    print(prompt_title)
    print(f"{prompt_hint}\n")
    for idx, genre_name in enumerate(genres, start=1):
        print(f"{idx}. {genre_name[:1].upper() + genre_name[1:]}")

    current_label = ", ".join(current_genres) if len(current_genres) > 0 else "не важно"
    while True:
        answer = input(f"\n{input_label} [{current_label}] >> ").strip()
        if answer == "":
            return current_genres

        parts = answer.split()
        selected_indexes = []
        for part in parts:
            try:
                index = int(part)
            except ValueError:
                selected_indexes = []
                break
            if 1 <= index <= len(genres):
                selected_indexes.append(index)
            else:
                selected_indexes = []
                break

        if len(selected_indexes) == 0:
            print("Введите номера жанров через пробел, например: 1 2 3")
            continue

        selected_genres = []
        for index in selected_indexes:
            genre_name = genres[index - 1]
            if genre_name not in selected_genres:
                selected_genres.append(genre_name)
        return selected_genres


def choose_or_create_criteria() -> tuple[str, dict] | None:
    """Дает выбрать сохраненный набор критериев или создать новый."""
    all_criteria = candidate_pool.load_candidate_criteria()
    criteria_names = sorted(all_criteria.keys())

    print("Сохраненные критерии:\n")
    print(" 0 >> Создать новый набор")
    for idx, name in enumerate(criteria_names, start=1):
        print(f" {idx} >> {candidate_pool.build_criteria_label(name, all_criteria[name])}")

    while True:
        answer = input("\nВыбор >> ").strip()
        try:
            select = int(answer)
        except ValueError:
            print("Введите номер пункта.")
            continue

        if 0 <= select <= len(criteria_names):
            break
        print("Такого пункта нет.")

    if select == 0:
        return create_criteria_interactive()

    name = criteria_names[select - 1]
    return name, all_criteria[name]


def choose_existing_criteria() -> tuple[str, dict] | None:
    """Дает выбрать только существующий набор критериев."""
    all_criteria = candidate_pool.load_candidate_criteria()
    criteria_names = sorted(all_criteria.keys())
    if len(criteria_names) == 0:
        print("Сохраненных критериев пока нет.")
        return None

    print("Сохраненные критерии:\n")
    for idx, name in enumerate(criteria_names, start=1):
        print(f" {idx} >> {candidate_pool.build_criteria_label(name, all_criteria[name])}")

    while True:
        answer = input("\nВыбор >> ").strip()
        try:
            select = int(answer)
        except ValueError:
            print("Введите номер пункта.")
            continue

        if 1 <= select <= len(criteria_names):
            break
        print("Такого пункта нет.")

    name = criteria_names[select - 1]
    return name, all_criteria[name]


def create_criteria_interactive() -> tuple[str, dict] | None:
    """Запрашивает новый набор критериев и сохраняет его."""
    all_criteria = candidate_pool.load_candidate_criteria()

    while True:
        criteria_name = input("Название набора критериев >> ").strip()
        if criteria_name == "":
            print("Название не должно быть пустым.")
            continue
        break

    current = all_criteria.get(criteria_name, {})
    country_default = current.get("country")
    country_answer = input(f"Страна [{format_optional_default(country_default)}] >> ").strip()
    country = country_answer if country_answer != "" else country_default
    count = prompt_optional_int("Сколько кандидатов собрать", current.get("count", 20), min_value=1)
    min_kp = prompt_optional_score("Минимальный рейтинг KP", current.get("min_kp"))
    min_imdb = prompt_optional_score("Минимальный рейтинг IMDb", current.get("min_imdb"))
    min_kp_votes = prompt_optional_int("Минимум голосов KP", current.get("min_kp_votes"))
    min_imdb_votes = prompt_optional_int("Минимум голосов IMDb", current.get("min_imdb_votes"))
    min_year = prompt_optional_year("Минимальный год", current.get("min_year"))
    max_year = prompt_optional_year("Максимальный год", current.get("max_year"))
    genres_default = current.get("genres", [])
    genres = choose_genres_by_numbers(genres_default)
    excluded_genres_default = current.get("excluded_genres", [])
    excluded_genres = choose_genres_by_numbers(
        excluded_genres_default,
        prompt_title="Выберите жанры, которые нужно исключить.",
        prompt_hint="Можно оставить пусто, тогда исключения по жанрам не будет.",
        input_label="Номера жанров для исключения",
    )

    criteria = {
        "country": country,
        "count": count,
        "min_kp": min_kp,
        "min_imdb": min_imdb,
        "min_kp_votes": min_kp_votes,
        "min_imdb_votes": min_imdb_votes,
        "min_year": min_year,
        "max_year": max_year,
        "genres": genres,
        "excluded_genres": excluded_genres,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    return candidate_pool.save_named_criteria(criteria_name, criteria)


def update_criteria_filters(criteria_name: str, current: dict) -> dict:
    """Интерактивно обновляет у набора критериев только блок фильтрации."""
    min_kp = prompt_optional_score("Минимальный рейтинг KP", current.get("min_kp"))
    genres = choose_genres_by_numbers(
        current.get("genres", []),
        prompt_title="Выберите жанры, которые должны быть у кандидата.",
        prompt_hint="Можно оставить пусто, тогда обязательных жанров не будет.",
        input_label="Номера жанров",
    )
    excluded_genres = choose_genres_by_numbers(
        current.get("excluded_genres", []),
        prompt_title="Выберите жанры, которые нужно исключить.",
        prompt_hint="Можно оставить пусто, тогда исключения по жанрам не будет.",
        input_label="Номера жанров для исключения",
    )
    return candidate_pool.patch_criteria_filters(
        criteria_name,
        current,
        min_kp=min_kp,
        genres=genres,
        excluded_genres=excluded_genres,
    )
