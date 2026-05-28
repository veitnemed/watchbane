import constant


def is_valid_features(features: dict) -> bool:
    return set(constant.FEATURES) == set(features.keys())


def is_correct_title(title):
    title = title.strip()
    if title == '':
        return False
    return len(set(constant.BAD_CHARACTERS) & set(title)) == 0


def is_correct_score(score: str):
    try:
        score_float = float(score)
        return 0 <= score_float <= 10
    except:
        return False


def is_correct_year(year: str) -> bool:
    try:
        year_int = int(year)
        return 2000 <= year_int <= constant.NOW_YEAR
    except:
        return False


def is_correct_main_menu_command(command: str):
    return command in constant.COMMANDS


def is_correct_votes(votes: str) -> bool:
    try:
        votes_int = int(votes)
        return votes_int >= 0
    except:
        return False


def is_valid_raw_meta(raw: dict) -> bool:
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
    try:
        score_int = int(score)
        return 0 <= score_int <= max_value
    except:
        return False


def is_origin_title(title: str) -> bool:
    import storage
    dataset = storage.load_dataset()
    title = title.strip()
    for k in dataset.keys():
        if k.lower() == title.lower():
            return False
    return True

def is_correct_select_menu(max_value: int, n: int) -> bool:
    """Проверка численного выбора меню и подменю"""
    try:
        n_int = int(n)
        return 0 <= n_int <= max_value
    except:
        return True
    
def is_correct_train_step(value: str) -> bool:
    if value.strip() == "":
        return True
    try:
        step = float(value)
        return 0 < step <= 1
    except ValueError:
        return False

def is_correct_plateau_score(value: str) -> bool:
    if value.strip() == "":
        return True
    try:
        score = int(value)
        return score > 0
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
