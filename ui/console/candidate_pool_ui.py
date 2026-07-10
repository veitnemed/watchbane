"""Интерактивный ввод для работы с пулом кандидатов."""

from datetime import datetime

from config import constant
from common import valid
from candidates import service as candidate_service
from candidates.models.keys import COMMON_POOL_CRITERIA_NAME
from candidates.pool.completeness import get_available_genres
from candidates.repositories.criteria_repository import (
    ensure_common_pool_criteria,
    load_candidate_criteria,
    patch_criteria_filters,
    save_named_criteria,
)


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
    criteria_name: str | None = None,
    prompt_title: str = "Жанры для поиска (по сохранённым данным pool): выберите по номерам через пробел.",
    prompt_hint: str = "Это фильтр по уже сохранённым кандидатам; он не запускает TMDb Discover.",
    input_label: str = "Номера жанров",
) -> list:
    """Дает выбрать жанры по номерам из списка pool (fallback — общий каталог)."""
    if current_genres is None:
        current_genres = []

    genres = candidate_service.get_search_genre_options_view(criteria_name)["genres"]
    used_catalog_fallback = False
    if len(genres) == 0:
        genres = get_available_genres()
        used_catalog_fallback = len(genres) > 0

    if len(genres) == 0:
        print("Список жанров пока пуст.")
        return current_genres

    print(prompt_title)
    print(f"{prompt_hint}\n")
    if used_catalog_fallback:
        print("(в pool жанров пока нет — показан общий каталог TMDb)\n")
    for idx, genre_name in enumerate(genres, start=1):
        print(f"{idx}. {genre_name}")

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


def get_common_pool_criteria_readonly() -> tuple[str, dict] | None:
    """Возвращает настройки общего pool без записи JSON."""
    criteria = load_candidate_criteria().get(COMMON_POOL_CRITERIA_NAME)
    if isinstance(criteria, dict) is False:
        return None
    return COMMON_POOL_CRITERIA_NAME, criteria


def choose_or_create_criteria() -> tuple[str, dict] | None:
    """Редактирует настройки сбора для единого общего pool."""
    return create_criteria_interactive()


def choose_existing_criteria() -> tuple[str, dict] | None:
    """Возвращает настройки общего pool для read-only сценариев."""
    selected = get_common_pool_criteria_readonly()
    if selected is None:
        print("Настройки общего pool пока не сохранены.")
    return selected


def create_criteria_interactive() -> tuple[str, dict] | None:
    """Запрашивает настройки сбора для общего pool и сохраняет их."""
    criteria_name, current = ensure_common_pool_criteria()
    country_default = current.get("country")
    country_answer = input(f"Страна [{format_optional_default(country_default)}] >> ").strip()
    country = country_answer if country_answer != "" else country_default
    count = prompt_optional_int("Сколько кандидатов собрать", current.get("count", 20), min_value=1)
    min_tmdb_score = prompt_optional_score(
        "Минимальный рейтинг TMDb",
        current.get("min_tmdb_score") or current.get("min_tmdb"),
    )
    min_year = prompt_optional_year("Минимальный год", current.get("min_year"))
    max_year = prompt_optional_year("Максимальный год", current.get("max_year"))
    genres_default = current.get("genres", [])
    genres = choose_genres_by_numbers(genres_default, criteria_name=criteria_name)
    excluded_genres_default = current.get("excluded_genres", [])
    excluded_genres = choose_genres_by_numbers(
        excluded_genres_default,
        criteria_name=criteria_name,
        prompt_title="Жанры для поиска (по сохранённым данным pool): выберите исключаемые жанры.",
        prompt_hint="Enter = оставить saved default. Это не пересобирает pool и не делает новый TMDb-запрос.",
        input_label="Номера жанров для исключения",
    )

    criteria = {
        "country": country,
        "count": count,
        "min_tmdb_score": min_tmdb_score,
        "min_year": min_year,
        "max_year": max_year,
        "genres": genres,
        "excluded_genres": excluded_genres,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    return save_named_criteria(criteria_name, criteria)


def update_criteria_filters(criteria_name: str, current: dict) -> dict:
    """Интерактивно обновляет у общего pool только блок фильтрации."""
    min_tmdb_score = prompt_optional_score(
        "Минимальный рейтинг TMDb",
        current.get("min_tmdb_score") or current.get("min_tmdb"),
    )
    genres = choose_genres_by_numbers(
        current.get("genres", []),
        criteria_name=criteria_name,
        prompt_title="Жанры для поиска (по сохранённым данным pool): выберите обязательные жанры.",
        prompt_hint="Enter = оставить saved default. Это не пересобирает pool и не делает новый TMDb-запрос.",
        input_label="Номера жанров",
    )
    excluded_genres = choose_genres_by_numbers(
        current.get("excluded_genres", []),
        criteria_name=criteria_name,
        prompt_title="Жанры для поиска (по сохранённым данным pool): выберите исключаемые жанры.",
        prompt_hint="Enter = оставить saved default. Это не пересобирает pool и не делает новый TMDb-запрос.",
        input_label="Номера жанров для исключения",
    )
    return patch_criteria_filters(
        criteria_name,
        current,
        min_tmdb_score=min_tmdb_score,
        genres=genres,
        excluded_genres=excluded_genres,
    )
