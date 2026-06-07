"""Собирает константы проекта: пути, поля, подписи и веса по умолчанию."""

from config import scheme
from config import tags_work

DATA_DIR = 'C:/DATA/movies-learn/'
FILE_NAME = 'C:/DATA/movies-learn/dataset.json'
WEIGHTS_JSON = 'C:/DATA/movies-learn/weights.json'
BACKUP_DIR = 'C:/BACKUP/movies-learn/BACKUP/'

DIR_META = 'C:/META/meta-movies-learn/'
META_JSON = 'C:/META/meta-movies-learn/meta_data.json'

DIR_TXT = 'C:/TXT_FILES/movies-learn/'
EDIT_EXCEL = 'C:/TXT_FILES/movies-learn/edit_dataset.xlsx'

STEPS_TRAIN = [0.05, 0.02, 0.01, 0.005, 0.001]
STEPS_TRAIN_MIX = [0.01, 0.05, 0.02, 0.01, 0.005]

MAIN_INFO = scheme.get_fields(scheme.MAIN_INFO)
RAW_SCORES = scheme.get_fields(scheme.RAW_SCORES)
TAGS_VIBE = scheme.get_fields(scheme.TAGS_VIBE)
TAGS_VIBE_SECTION = scheme.TAGS_VIBE

COMPUTED_SCORES = scheme.get_computed_fields()

CSV_FIELDS = MAIN_INFO + RAW_SCORES + TAGS_VIBE
FEATURES = COMPUTED_SCORES + TAGS_VIBE
RAW_META_FIELDS = RAW_SCORES
FEATURES_CONST = COMPUTED_SCORES

ONLY_SCORES = CSV_FIELDS.copy(); ONLY_SCORES.remove("title"); ONLY_SCORES.remove("year")

SECTION_LABELS = {
    scheme.MAIN_INFO: "Основная информация",
    scheme.RAW_SCORES: "Исходные данные",
    scheme.TAGS_VIBE: "Теги вайба"
}


FIELD_LABELS = {
    "title": "Название",
    "user_score": "Ваша оценка",
    "year": "Год выхода",
    "kp_score": "Рейтинг Кинопоиска",
    "kp_votes": "Количество голосов Кинопоиска",
    "imdb_score": "Рейтинг IMDb",
    "imdb_votes": "Количество голосов IMDb",
    "kp_popularity": "Популярность Кинопоиска",
    "imdb_popularity": "Популярность IMDb"
}
FIELD_LABELS.update(tags_work.get_tag_labels())

TAG_RULES = tags_work.get_tag_rules()

DEFAULT_WEIGHTS = {
    feature: round(1 / len(FEATURES), 4)
    for feature in FEATURES
}

TRANSLATION = {
    'features': {
        "kp_score": "Kinopoisk score",
        "kp_popularity": "Kinopoisk popularity",
        "imdb_score": "IMDb score",
        "imdb_popularity": "IMDb popularity"
    },
    'meta features': {
        "year": "Year",
        "kp_score": "Kinopoisk score",
        "kp_votes": "Kinopoisk votes",
        "imdb_score": "IMDb score",
        "imdb_votes": "IMDb votes"
    }
}
TRANSLATION["features"].update(tags_work.get_tag_translations())

COMMANDS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]
BAD_CHARACTERS = ",.'][@#$%^&*()?"
THRESHOLD = 6.5
NOW_YEAR = 2026
STEP = 0.01
