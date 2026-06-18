"""Собирает записи фильмов и добавляет их в dataset/meta."""

from config import constant
from config import scheme
from common import format_score as format
from common import valid
from data_work.dataset_records import add_dataset_record
from data_work.storage_data import load_dataset, save_dataset
from data_work.storage_normalize import (
    normalize_csv_row,
    normalize_main_info,
    normalize_raw_scores,
)


def rework_computed():
    """Пересчитывает вычисленные признаки у всех фильмов."""
    data = load_dataset()

    for title, info in data.items():
        raw_scores = normalize_raw_scores(info["raw_scores"])
        main_info = normalize_main_info(info["main_info"])
        info["computed_scores"] = format.raw_to_struct(raw_scores, main_info)

    save_dataset(data)


def rework_formated_scores() -> int:
    """Пересчитывает форматируемые raw-признаки у всех фильмов."""
    data = load_dataset()
    raw_schema = scheme.get_schema(scheme.RAW_SCORES)
    updated_count = 0

    for title, info in data.items():
        raw_scores = normalize_raw_scores(info["raw_scores"])
        main_info = normalize_main_info(info["main_info"])

        if "computed_scores" not in info:
            info["computed_scores"] = {}

        for raw_feature, settings in raw_schema.items():
            formated = settings["formated"]
            if formated is None:
                continue

            info["computed_scores"][formated] = format.FORMATTERS[formated](raw_scores, main_info)

        updated_count += 1

    save_dataset(data)
    return updated_count


def add_movie(movie: dict, *, meta_payload=None, pool_candidate=None, print_message: bool = True):
    """Добавляет фильм в датасет."""
    result = add_dataset_record(
        movie,
        meta_payload=meta_payload,
        source_name="add_movie",
        pool_candidate=pool_candidate,
    )
    if print_message:
        print(result.message)
    return result


def add_movies(title: str, user_score: str, raw_scores: dict, tags_vibe: dict, genre_tags: dict = None) -> bool:
    """Добавляет фильм через старый формат аргументов."""
    main_info = {}
    main_info["title"] = title
    main_info["user_score"] = user_score
    main_info["year"] = raw_scores.get("year", constant.NOW_YEAR)
    raw_scores.pop("year", None)

    movie = {}
    movie["main_info"] = main_info
    movie["raw_scores"] = raw_scores
    movie[constant.TAGS_VIBE_SECTION] = tags_vibe
    movie[constant.GENRE_SECTION] = {} if genre_tags is None else genre_tags

    return add_movie(movie).ok


def build_movie_from_row(row: dict, row_number: int) -> dict:
    """Собирает объект фильма из строки таблицы."""
    row = normalize_csv_row(row)
    title = row["title"].strip()
    user_score = row["user_score"].strip()
    year = row["year"].strip()

    if valid.is_correct_title(title) is False:
        print(f'Строка {row_number}: некорректное название')
        return None

    if valid.is_correct_score(user_score) is False:
        print(f'Строка {row_number}: некорректное значение user_score')
        return None

    if valid.is_correct_year(year) is False:
        print(f'Line {row_number}: incorrect year')
        return None

    raw_scores = {}
    for feature in constant.RAW_SCORES:
        value = row[feature].strip()
        if feature == "year":
            if valid.is_correct_year(value) is False:
                print(f'Строка {row_number}: некорректный год')
                return None
            raw_scores[feature] = int(value)
        elif feature.endswith("_votes"):
            if valid.is_correct_votes(value) is False:
                print(f'Строка {row_number}: некорректное количество голосов')
                return None
            raw_scores[feature] = int(value)
        else:
            if valid.is_correct_score(value) is False:
                print(f'Строка {row_number}: некорректное значение {feature}')
                return None
            raw_scores[feature] = valid.parse_float(value)

    tags_vibe = {}
    tags_schema = scheme.get_schema(scheme.TAGS_VIBE)
    for feature in constant.TAGS_VIBE:
        value = row[feature].strip()
        max_value = tags_schema[feature].get("max_value", 1)
        if valid.is_tags_score(value, max_value) is False:
            print(f'Строка {row_number}: некорректное значение {feature}')
            return None
        tags_vibe[feature] = int(value)

    genre_values = {}
    genre_schema = scheme.get_schema(scheme.GENRE)
    for feature in constant.GENRE:
        value = row[feature].strip()
        max_value = genre_schema[feature].get("max_value", 1)
        if valid.is_tags_score(value, max_value) is False:
            print(f'Строка {row_number}: некорректное значение {feature}')
            return None
        genre_values[feature] = int(value)

    main_info = {}
    main_info["title"] = title
    main_info["user_score"] = valid.parse_float(user_score)
    main_info["year"] = int(year)

    movie = {}
    movie["main_info"] = main_info
    movie["raw_scores"] = raw_scores
    movie[constant.TAGS_VIBE_SECTION] = tags_vibe
    movie[constant.GENRE_SECTION] = genre_values
    return movie
