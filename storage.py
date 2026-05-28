import csv
import json
import os
from datetime import datetime

import constant
import format_score as format
import scheme
import valid


def is_json_exists(file_name):
    """Проверяет, существует ли файл по переданному пути."""
    return os.path.exists(file_name)


def init_dataset():
    """Создает пустой файл датасета, если он еще не существует."""
    empty_dict = {}

    if is_json_exists(constant.FILE_NAME) is False:
        os.makedirs(constant.DATA_DIR, exist_ok=True)
        with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
            json.dump(empty_dict, file, ensure_ascii=False, indent=4)


def init_meta():
    """Создает пустой файл метаданных, если он еще не существует."""
    empty_dict = {}

    if is_json_exists(constant.META_JSON) is False:
        os.makedirs(constant.DIR_META, exist_ok=True)
        with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
            json.dump(empty_dict, file, ensure_ascii=False, indent=4)


def load_meta() -> dict:
    """Загружает метаданные фильмов из JSON-файла."""
    with open(constant.META_JSON, 'r', encoding='UTF-8') as file:
        return json.load(file)


def save_meta(meta: dict):
    """Сохраняет метаданные фильмов в JSON-файл."""
    with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
        json.dump(meta, file, ensure_ascii=False, indent=4)


def load_dataset() -> list:
    """Загружает список фильмов из JSON-файла датасета."""
    with open(constant.FILE_NAME, 'r', encoding='UTF-8') as file:
        return json.load(file)


def save_dataset(data: list):
    """Сохраняет список фильмов в JSON-файл датасета."""
    with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def is_origin_title(new_title: str) -> bool:
    """Проверяет, что фильма с таким названием еще нет в датасете."""
    data = load_dataset()

    for title in data.keys():
        if title.strip().lower() == new_title.strip().lower():
            return False
    return True


def normalize_main_info(main_info: dict) -> dict:
    normalized = {}
    for feature in constant.MAIN_INFO:
        if feature == "title":
            normalized[feature] = str(main_info[feature]).strip()
        elif feature == "year":
            normalized[feature] = int(main_info[feature])
        else:
            normalized[feature] = float(main_info[feature])
    return normalized


def normalize_raw_scores(raw: dict) -> dict:
    normalized = {}
    for feature in constant.RAW_SCORES:
        if feature.endswith("_votes"):
            normalized[feature] = int(raw[feature])
        else:
            normalized[feature] = float(raw[feature])
    return normalized


def is_valid_tags_vibe(tags_vibe: dict) -> bool:
    tags_schema = scheme.get_schema(scheme.TAGS_VIBE)
    if set(tags_vibe.keys()) != set(tags_schema.keys()):
        return False

    for feature, value in tags_vibe.items():
        max_value = tags_schema[feature].get("max_value", 1)
        if valid.is_tags_score(value, max_value) is False:
            return False
    return True


def add_movies_to_meta(main_info: dict, raw: dict) -> bool:
    """Добавляет постоянные raw-данные фильма в файл метаданных."""
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
    data = load_dataset()

    for title, info in data.items():
        raw_scores = normalize_raw_scores(info["raw_scores"])
        main_info = normalize_main_info(info["main_info"])
        info["computed_scores"] = format.raw_to_struct(raw_scores, main_info)

    save_dataset(data)


def rework_formated_scores() -> int:
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
    """Добавляет фильм в датасет, используя постоянные raw-поля из meta."""
    main_info = movie["main_info"]
    input_raw_scores = movie["raw_scores"]
    tags_vibe = movie[constant.TAGS_VIBE_SECTION]

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
    """Поддерживает старый формат вызова добавления фильма через add_movie."""
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
    """Очищает датасет и оставляет в файле пустой список."""
    empty_dict = {}
    with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
        json.dump(empty_dict, file, ensure_ascii=False, indent=4)


def clean_meta():
    empty_dict = {}
    with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
        json.dump(empty_dict, file, ensure_ascii=False, indent=4)


def init_weights():
    """Создает файл весов модели со значениями по умолчанию."""
    if is_json_exists(constant.WEIGHTS_JSON) is False:
        with open(constant.WEIGHTS_JSON, 'w', encoding='UTF-8') as file:
            json.dump(constant.DEFAULT_WEIGHTS, file, ensure_ascii=False, indent=4)


def load_weights() -> list:
    """Загружает веса модели из JSON-файла."""
    with open(constant.WEIGHTS_JSON, 'r', encoding='UTF-8') as file:
        return json.load(file)


def save_weights(data: dict):
    """Сохраняет веса модели в JSON-файл."""
    with open(constant.WEIGHTS_JSON, 'w', encoding='UTF-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def uppdate_weights(weights: dict):
    """Перезаписывает сохраненные веса модели."""
    save_weights(weights)


def init_txt():
    """Создает пустой txt-файл для старого импорта, если он еще не существует."""
    if is_json_exists(constant.TXT_INPUT) is False:
        os.makedirs(constant.DIR_TXT, exist_ok=True)
        with open(constant.TXT_INPUT, 'w', encoding='UTF-8') as file:
            return


def init_csv():
    """Создает CSV-файл для импорта с заголовками, если он еще не существует."""
    if is_json_exists(constant.CSV_INPUT) is False:
        os.makedirs(constant.DIR_TXT, exist_ok=True)
        with open(constant.CSV_INPUT, 'w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=constant.CSV_FIELDS, delimiter=';')
            writer.writeheader()


def export_dataset_to_csv() -> bool:
    data = load_dataset()
    meta = load_meta()
    os.makedirs(constant.DIR_TXT, exist_ok=True)

    try:
        with open(constant.EDIT_CSV, 'w', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=constant.CSV_FIELDS, delimiter=';')
            writer.writeheader()

            for movie in data.values():
                row = {}
                for feature in constant.MAIN_INFO:
                    row[feature] = movie["main_info"][feature]
                for feature in constant.RAW_SCORES:
                    row[feature] = movie["raw_scores"][feature]
                for feature in constant.TAGS_VIBE:
                    row[feature] = movie[constant.TAGS_VIBE_SECTION][feature]
                writer.writerow(row)

            if len(data) == 0 and len(meta) > 0:
                for movie in meta.values():
                    row = {}
                    for feature in constant.MAIN_INFO:
                        row[feature] = movie["main_info"][feature]
                    for feature in constant.RAW_SCORES:
                        row[feature] = movie["raw_scores"][feature]
                    for feature in constant.TAGS_VIBE:
                        row[feature] = ""
                    writer.writerow(row)
    except PermissionError:
        print(f'Не удалось открыть CSV для записи: {constant.EDIT_CSV}')
        print('Закрой файл в Excel или другой программе и попробуй снова.')
        return False

    print(f'CSV для редактирования сохранен: {constant.EDIT_CSV}')
    if len(data) == 0 and len(meta) > 0:
        print(f'Dataset пустой, но в meta найдено записей: {len(meta)}')
        print('В edit CSV выгружен шаблон из meta. Заполни колонки tags_vibe и импортируй пунктом 6.')
    return True


def build_movie_from_row(row: dict, row_number: int) -> dict:
    """Преобразует строку CSV в структуру фильма для add_movie."""
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
            raw_scores[feature] = float(value)

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
    main_info["user_score"] = float(user_score)
    main_info["year"] = int(year)

    movie = {}
    movie["main_info"] = main_info
    movie["raw_scores"] = raw_scores
    movie[constant.TAGS_VIBE_SECTION] = tags_vibe
    return movie


def input_csv(file_name: str = None) -> bool:
    """Импортирует фильмы из CSV-файла в датасет."""
    if file_name is None:
        file_name = constant.CSV_INPUT

    added_count = 0

    with open(file_name, 'r', encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file, delimiter=';')

        if reader.fieldnames is None:
            print('CSV-файл пуст!')
            return False

        if reader.fieldnames != constant.CSV_FIELDS:
            print('Ошибка CSV! Заголовки не совпадают с ожидаемыми')
            print('Ожидались:', constant.CSV_FIELDS)
            print('Получены:', reader.fieldnames)
            return False

        for row_number, row in enumerate(reader, start=2):
            if all(row[field].strip() == "" for field in constant.CSV_FIELDS):
                continue

            movie = build_movie_from_row(row, row_number)
            if movie is None:
                return False

            if add_movie(movie) is False:
                print(f'Ошибка импорта CSV! Строка {row_number}')
                return False

            added_count += 1

    if added_count == 0:
        print('Нет строк для импорта из CSV')
        return False

    print(f'Импорт CSV завершен. Добавлено записей: {added_count}')
    return True


def input_edit_csv() -> bool:
    added_count = 0
    skipped_count = 0
    rows_count = 0

    try:
        with open(constant.EDIT_CSV, 'r', encoding='utf-8-sig', newline='') as file:
            reader = csv.DictReader(file, delimiter=';')

            if reader.fieldnames is None:
                print('Edit CSV пуст!')
                return False

            if reader.fieldnames != constant.CSV_FIELDS:
                print('Ошибка edit CSV! Заголовки не совпадают с ожидаемыми')
                print('Ожидались:', constant.CSV_FIELDS)
                print('Получены:', reader.fieldnames)
                return False

            for row_number, row in enumerate(reader, start=2):
                values = [row[field].strip() for field in constant.CSV_FIELDS]

                if all(value == "" for value in values):
                    continue

                rows_count += 1

                if any(value == "" for value in values):
                    print(f'Строка {row_number}: пропущена, заполнены не все поля')
                    skipped_count += 1
                    continue

                movie = build_movie_from_row(row, row_number)
                if movie is None:
                    return False

                if add_movie(movie) is False:
                    print(f'Ошибка импорта edit CSV! Строка {row_number}')
                    return False

                added_count += 1
    except PermissionError:
        print(f'Не удалось прочитать CSV: {constant.EDIT_CSV}')
        print('Закрой файл в Excel или другой программе и попробуй снова.')
        return False

    if rows_count == 0:
        print('В edit CSV нет записей для импорта.')
        return False

    print(f'Импорт edit CSV завершен. Добавлено: {added_count}, пропущено: {skipped_count}')
    return added_count > 0 and skipped_count == 0


def replace_dataset_from_edit_csv() -> bool:
    if os.path.exists(constant.EDIT_CSV) is False:
        print(f'Файл для редактирования не найден: {constant.EDIT_CSV}')
        return False

    old_dataset = load_dataset()
    old_meta = load_meta()
    create_backup()
    clean_dataset()
    clean_meta()

    if input_edit_csv() is False:
        save_dataset(old_dataset)
        save_meta(old_meta)
        print('Импорт отменен. Старый dataset и meta восстановлены.')
        return False

    rework_formated_scores()
    print('Dataset пересобран из edit CSV.')
    return True


def input_txt() -> bool:
    """Импортирует фильмы из txt-файла в датасет через старый формат с разделителем ;."""
    expected_len = len(constant.CSV_FIELDS)
    added_count = 0
    with open(constant.TXT_INPUT, 'r', encoding='utf-8-sig') as file:
        data = file.readlines()

        if len(data) == 0:
            print('Текстовый файл пуст!')
            return False

    for idx, line in enumerate(data):
        if line.strip() == "":
            continue

        params = [param.strip() for param in line.strip().split(';')]

        if len(params) != expected_len:
            print(f'Ошибка парсинга из текстового файла! Строка {idx + 1}')
            return False

        if params[0].strip().lower() == 'title':
            continue

        row = {}
        for field, value in zip(constant.CSV_FIELDS, params):
            row[field] = value

        movie = build_movie_from_row(row, idx + 1)
        if movie is None:
            return False

        result = add_movie(movie)
        if result is False:
            print(f'Ошибка парсинга! Строка {idx + 1}')
            return False
        added_count += 1

    if added_count == 0:
        print('Нет строк для импорта')
        return False

    print(f'Импорт завершен. Добавлено записей: {added_count}')
    return True


def restart_txt():
    """Очищает txt-файл для импорта."""
    os.makedirs(constant.DIR_TXT, exist_ok=True)
    with open(constant.TXT_INPUT, 'w', encoding='UTF-8') as file:
        return


def restart_csv():
    """Очищает CSV-файл для импорта и оставляет только заголовки."""
    os.makedirs(constant.DIR_TXT, exist_ok=True)
    with open(constant.CSV_INPUT, 'w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=constant.CSV_FIELDS, delimiter=';')
        writer.writeheader()


def create_backup():
    """Создает резервную копию текущего датасета."""
    dataset = load_dataset()
    date_name = datetime.now().strftime('%d-%m-%Y %H-%M-%S')
    backup_file = constant.BACKUP_DIR + date_name + '.json'
    if is_json_exists(backup_file) is False:
        os.makedirs(constant.BACKUP_DIR, exist_ok=True)

    with open(backup_file, 'w', encoding='UTF-8') as file:
        json.dump(dataset, file, ensure_ascii=False, indent=4)


def title_in_meta(title: str) -> bool:
    """Проверяет, есть ли фильм с таким названием в метаданных."""
    title = title.strip()
    meta = load_meta()

    return any(meta_title.lower() == title.lower() for meta_title in meta.keys())


def get_meta_obj(title: str) -> dict:
    """Возвращает объект метаданных фильма по названию."""
    title = title.strip()
    meta = load_meta()

    for meta_title, obj in meta.items():
        if meta_title.lower() == title.lower():
            return obj
    return None
