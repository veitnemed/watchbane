"""Проверяет корректность пользовательского ввода и структур данных."""

from config import constant


def parse_float(value) -> float:
    """Преобразует строку с точкой или запятой в число."""
    return float(str(value).replace(",", "."))


def is_valid_features(features: dict) -> bool:
    """Проверяет, что набор признаков совпадает со схемой модели."""
    return set(constant.FEATURES) == set(features.keys())


def is_correct_title(title):
    """Проверяет корректность названия."""
    title = title.strip()
    if title == '':
        return False
    return len(set(constant.BAD_CHARACTERS) & set(title)) == 0


def is_correct_score(score: str):
    """Проверяет корректность оценки."""
    try:
        score_float = parse_float(score)
        return 0 <= score_float <= 10
    except:
        return False


def is_correct_year(year: str) -> bool:
    """Проверяет корректность года."""
    try:
        year_int = int(year)
        return 2000 <= year_int <= constant.NOW_YEAR
    except:
        return False


def is_correct_main_menu_command(command: str):
    """Проверяет команду главного меню."""
    return command in constant.COMMANDS


def is_correct_votes(votes: str) -> bool:
    """Проверяет количество голосов."""
    try:
        votes_int = int(votes)
        return votes_int >= 0
    except:
        return False


def is_valid_raw_meta(raw: dict) -> bool:
    """Проверяет сырые данные для meta."""
    if set(raw.keys()) != set(constant.RAW_META_FIELDS):
        return False

    if is_correct_score(raw["kp_score"]) is False:
        return False

    if is_correct_votes(raw["imdb_votes"]) is False:
        return False

    if is_correct_votes(raw["kp_votes"]) is False:
        return False

    if is_correct_score(raw["imdb_score"]) is False:
        return False

    return True


def is_tags_score(score: str, max_value: int = 1) -> bool:
    """Проверяет значение тега."""
    try:
        score_int = int(score)
        if max_value is None:
            return score_int >= 0
        return 0 <= score_int <= max_value
    except:
        return False


def is_origin_title(title: str) -> bool:
    """Проверяет, что такого названия еще нет."""
    from data_work import storage

    dataset = storage.load_dataset()
    title = title.strip()
    for k in dataset.keys():
        if k.lower() == title.lower():
            return False
    return True

def is_correct_select_menu(max_value: int, n: int) -> bool:
    """Проверяет выбор пункта меню."""
    try:
        n_int = int(n)
        return 0 <= n_int <= max_value
    except:
        return True
    
def is_correct_train_step(value: str) -> bool:
    """Проверяет шаг обучения."""
    if value.strip() == "":
        return True
    try:
        step = parse_float(value)
        return 0 < step <= 1
    except ValueError:
        return False

def is_correct_plateau_score(value: str) -> bool:
    """Проверяет число попыток до плато."""
    if value.strip() == "":
        return True
    try:
        score = int(value)
        return score > 0
    except ValueError:
        return False

def is_correct_noise_delta(value: str) -> bool:
    """Проверяет максимальное случайное смещение оценки для шумового эксперимента."""
    if value.strip() == "":
        return True
    try:
        delta = parse_float(value)
        return 0 <= delta <= 10
    except ValueError:
        return False

def is_correct_noise_runs(value: str) -> bool:
    """Проверяет количество повторов шумового эксперимента."""
    if value.strip() == "":
        return True
    try:
        runs = int(value)
        return runs > 0
    except ValueError:
        return False

def is_correct_top_n(value: str) -> bool:
    """Проверяет число объектов для топа ошибок."""
    try:
        top_n = int(value)
        return top_n > 0
    except ValueError:
        return False

VALIDATORS = {
    "score": is_correct_score,
    "year": is_correct_year,
    "votes": is_correct_votes,
    "tags_score": is_tags_score,
    "title": is_correct_title,
    "origin_title": is_origin_title
}
