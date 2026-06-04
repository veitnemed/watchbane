"""Читает, сохраняет и преобразует основные данные проекта."""

import json
import os
from datetime import datetime

from config import constant
from core import format_score as format
from config import scheme
from core import valid


LEGACY_TAG_FIELDS = {
    "has_psyhology": "has_psychology",
    "has_relationship_focus": "has_relationships",
    "has_romantic_tension": "has_romantic_pursuit",
    "has_love_tension": "has_romantic_pursuit",
}
REMOVED_TAG_FIELDS = {"has_mystic"}


def normalize_tags_vibe(tags_vibe: dict) -> dict:
    """Приводит теги фильма к актуальной схеме."""
    normalized = {feature: 0 for feature in constant.TAGS_VIBE}
    for feature, value in tags_vibe.items():
        if feature in normalized:
            normalized[feature] = value
    for old_feature, active_feature in LEGACY_TAG_FIELDS.items():
        if old_feature in tags_vibe and active_feature in normalized and active_feature not in tags_vibe:
            normalized[active_feature] = tags_vibe[old_feature]
    return normalized


def normalize_movie_tags(movie: dict) -> dict:
    """Нормализует теги внутри записи фильма."""
    if constant.TAGS_VIBE_SECTION in movie:
        movie[constant.TAGS_VIBE_SECTION] = normalize_tags_vibe(movie[constant.TAGS_VIBE_SECTION])
    return movie


def normalize_csv_row(row: dict) -> dict:
    """Приводит строку CSV к актуальным полям."""
    normalized = {feature: value for feature, value in row.items() if feature not in REMOVED_TAG_FIELDS}
    for old_feature, active_feature in LEGACY_TAG_FIELDS.items():
        if active_feature in constant.TAGS_VIBE and active_feature not in normalized and old_feature in normalized:
            normalized[active_feature] = normalized[old_feature]
        normalized.pop(old_feature, None)
    for feature in constant.TAGS_VIBE:
        normalized.setdefault(feature, "0")
    return normalized


def is_supported_csv_fields(fieldnames: list) -> bool:
    """Проверяет заголовки CSV-файла."""
    normalized = normalize_csv_row({field: "" for field in fieldnames})
    return all(field in normalized for field in constant.CSV_FIELDS)


def is_json_exists(file_name):
    """Проверяет существование JSON-файла."""
    return os.path.exists(file_name)


def open_file(file_name: str) -> None:
    """Открывает файл системной программой Windows."""
    os.startfile(file_name)


def is_file_writable(file_name: str) -> bool:
    """Проверяет, можно ли записывать в файл."""
    try:
        with open(file_name, 'a', encoding='UTF-8'):
            return True
    except PermissionError:
        return False


def init_dataset():
    """Создает файл датасета, если его нет."""
    empty_dict = {}

    if is_json_exists(constant.FILE_NAME) is False:
        os.makedirs(constant.DATA_DIR, exist_ok=True)
        with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
            json.dump(empty_dict, file, ensure_ascii=False, indent=4)


def init_meta():
    """Создает файл meta, если его нет."""
    empty_dict = {}

    if is_json_exists(constant.META_JSON) is False:
        os.makedirs(constant.DIR_META, exist_ok=True)
        with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
            json.dump(empty_dict, file, ensure_ascii=False, indent=4)


def load_meta() -> dict:
    """Загружает meta из JSON-файла."""
    with open(constant.META_JSON, 'r', encoding='utf-8-sig') as file:
        return json.load(file)


def save_meta(meta: dict):
    """Сохраняет meta в JSON-файл."""
    with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
        json.dump(meta, file, ensure_ascii=False, indent=4)


def load_dataset() -> list:
    """Загружает датасет из JSON-файла."""
    with open(constant.FILE_NAME, 'r', encoding='utf-8-sig') as file:
        data = json.load(file)
    for movie in data.values():
        normalize_movie_tags(movie)
    return data


def save_dataset(data: list):
    """Сохраняет датасет в JSON-файл."""
    with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
        normalized = {title: normalize_movie_tags(movie) for title, movie in data.items()}
        json.dump(normalized, file, ensure_ascii=False, indent=4)


def is_origin_title(new_title: str) -> bool:
    """Проверяет, что такого названия еще нет."""
    data = load_dataset()

    for title in data.keys():
        if title.strip().lower() == new_title.strip().lower():
            return False
    return True


def normalize_main_info(main_info: dict) -> dict:
    """Приводит основные данные фильма к нужным типам."""
    normalized = {}
    for feature in constant.MAIN_INFO:
        if feature == "title":
            normalized[feature] = str(main_info[feature]).strip()
        elif feature == "year":
            normalized[feature] = int(main_info[feature])
        else:
            normalized[feature] = valid.parse_float(main_info[feature])
    return normalized


def normalize_raw_scores(raw: dict) -> dict:
    """Приводит сырые оценки и голоса к нужным типам."""
    normalized = {}
    for feature in constant.RAW_SCORES:
        if feature.endswith("_votes"):
            normalized[feature] = int(raw[feature])
        else:
            normalized[feature] = valid.parse_float(raw[feature])
    return normalized


def is_valid_tags_vibe(tags_vibe: dict) -> bool:
    """Проверяет секцию тегов фильма."""
    tags_schema = scheme.get_schema(scheme.TAGS_VIBE)
    if set(tags_vibe.keys()) != set(tags_schema.keys()):
        return False

    for feature, value in tags_vibe.items():
        max_value = tags_schema[feature].get("max_value", 1)
        if valid.is_tags_score(value, max_value) is False:
            return False
    return True


def add_movies_to_meta(main_info: dict, raw: dict) -> bool:
    """Добавляет постоянные raw-данные фильма в meta."""
    title = str(main_info["title"]).strip()
    meta = load_meta()

    if valid.is_correct_title(title) is False:
        print('Ошибка добавления в meta! Некорректное название')
        return False

    if valid.is_correct_score(str(main_info["user_score"])) is False:
        print('Ошибка добавления в meta! Некорректное значение user_score')
        return False

    if valid.is_correct_year(str(main_info["year"])) is False:
        print('Ошибка добавления в meta! Некорректный год')
        return False

    if valid.is_valid_raw_meta(raw) is False:
        print('Ошибка добавления в meta! Некорректные raw-данные')
        return False

    meta_obj = {}
    meta_obj["main_info"] = normalize_main_info(main_info)
    meta_obj["raw_scores"] = normalize_raw_scores(raw)
    meta[title] = meta_obj

    save_meta(meta)
    return True

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


def clean_dataset():
    """Очищает датасет."""
    empty_dict = {}
    with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
        json.dump(empty_dict, file, ensure_ascii=False, indent=4)


def clean_meta():
    """Очищает meta."""
    empty_dict = {}
    with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
        json.dump(empty_dict, file, ensure_ascii=False, indent=4)


def init_weights():
    """Создает файл весов, если его нет."""
    if is_json_exists(constant.WEIGHTS_JSON) is False:
        with open(constant.WEIGHTS_JSON, 'w', encoding='UTF-8') as file:
            json.dump(constant.DEFAULT_WEIGHTS, file, ensure_ascii=False, indent=4)


def load_weights() -> list:
    """Загружает веса модели."""
    with open(constant.WEIGHTS_JSON, 'r', encoding='utf-8-sig') as file:
        weights = json.load(file)
    normalized = {}
    for feature in constant.FEATURES:
        normalized[feature] = weights.get(feature, constant.DEFAULT_WEIGHTS[feature])
        for old_feature, active_feature in LEGACY_TAG_FIELDS.items():
            if active_feature == feature and old_feature in weights and feature not in weights:
                normalized[feature] = weights[old_feature]
                break
    return normalized


def save_weights(data: dict):
    """Сохраняет веса модели."""
    with open(constant.WEIGHTS_JSON, 'w', encoding='UTF-8') as file:
        normalized = {feature: data.get(feature, constant.DEFAULT_WEIGHTS[feature]) for feature in constant.FEATURES}
        json.dump(normalized, file, ensure_ascii=False, indent=4)


def uppdate_weights(weights: dict):
    """Перезаписывает веса модели."""
    save_weights(weights)


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


def create_backup():
    """Создает резервную копию датасета."""
    dataset = load_dataset()
    date_name = datetime.now().strftime('%d-%m-%Y %H-%M-%S-%f')
    backup_file = constant.BACKUP_DIR + date_name + '.json'
    if is_json_exists(backup_file) is False:
        os.makedirs(constant.BACKUP_DIR, exist_ok=True)

    with open(backup_file, 'w', encoding='UTF-8') as file:
        json.dump(dataset, file, ensure_ascii=False, indent=4)


def title_in_meta(title: str) -> bool:
    """Проверяет наличие названия в meta."""
    title = title.strip()
    meta = load_meta()

    return any(meta_title.lower() == title.lower() for meta_title in meta.keys())


def get_meta_obj(title: str) -> dict:
    """Возвращает запись meta по названию."""
    title = title.strip()
    meta = load_meta()

    for meta_title, obj in meta.items():
        if meta_title.lower() == title.lower():
            return obj
    return None

def init_all_dates():
    """Инициализирует все рабочие файлы данных."""
    init_meta()
    init_dataset()
    init_weights()
    create_backup()

def get_all_titles() -> list:
    """Возвращает список всех названий в датасете."""

    return list(load_dataset().keys())
