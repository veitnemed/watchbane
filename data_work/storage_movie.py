"""Собирает записи фильмов и добавляет их в dataset/meta."""

from config import constant
from config import scheme
from core import format_score as format
from core import valid
from data_work.storage_data import add_movies_to_meta, get_meta_obj, is_origin_title, load_dataset, save_dataset
from data_work.storage_normalize import (
    is_valid_tags_vibe,
    normalize_csv_row,
    normalize_main_info,
    normalize_raw_scores,
    normalize_tags_vibe,
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


def add_movie(movie: dict) -> bool:
    """Добавляет фильм в датасет."""
    main_info = movie["main_info"]
    input_raw_scores = movie["raw_scores"]
    tags_vibe = normalize_tags_vibe(movie[constant.TAGS_VIBE_SECTION])

    title = str(main_info["title"]).strip()
    user_score = main_info["user_score"]

    if valid.is_correct_title(title) is False:
        print('Ошибка добавления! Некорректное название')
        return False

    if is_origin_title(title) is False:
        print('Ошибка добавления! Такой объект уже добавлен')
        return False

    if valid.is_correct_score(str(user_score)) is False:
        print('Ошибка добавления! Некорректное значение user_score')
        return False

    if valid.is_correct_year(str(main_info["year"])) is False:
        print('Error add movie! Incorrect year')
        return False

    if is_valid_tags_vibe(tags_vibe) is False:
        print('Ошибка добавления! Некорректные tags_vibe')
        return False

    if is_valid_tags_vibe(tags_vibe) is False:
        print('Ошибка добавления! Неверное значение субъективных параметров')
        return False

    meta_obj = get_meta_obj(title)
    if meta_obj is None:
        if valid.is_valid_raw_meta(input_raw_scores) is False:
            print('Ошибка добавления! Некорректные raw_scores')
            return False

        raw_scores = normalize_raw_scores(input_raw_scores)

        if add_movies_to_meta(main_info, raw_scores) is False:
            return False
    else:
        raw_scores = meta_obj.get("raw_scores", meta_obj.get("raw"))

    raw_scores = normalize_raw_scores(raw_scores)
    new_main_info = normalize_main_info(main_info)
    computed_scores = format.raw_to_struct(raw_scores, new_main_info)
    features = {}
    for feature in computed_scores:
        features[feature] = computed_scores[feature]
    for feature, value in format.tags_to_features(tags_vibe).items():
        features[feature] = value

    if valid.is_valid_features(features) is False:
        print('Ошибка добавления! Не хватает параметров')
        print('Ожидались:', constant.FEATURES)
        print('Получены:', list(features.keys()))
        return False

    data = load_dataset()

    new_movie = {}
    new_movie["main_info"] = new_main_info
    new_movie["raw_scores"] = raw_scores
    new_movie["computed_scores"] = computed_scores
    new_movie[constant.TAGS_VIBE_SECTION] = tags_vibe

    data[title] = new_movie
    save_dataset(data)
    return True


def add_movies(title: str, user_score: str, raw_scores: dict, tags_vibe: dict) -> bool:
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

    return add_movie(movie)


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

    main_info = {}
    main_info["title"] = title
    main_info["user_score"] = valid.parse_float(user_score)
    main_info["year"] = int(year)

    movie = {}
    movie["main_info"] = main_info
    movie["raw_scores"] = raw_scores
    movie[constant.TAGS_VIBE_SECTION] = tags_vibe
    return movie
