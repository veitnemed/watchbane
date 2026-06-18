"""Собирает константы проекта: пути, поля, подписи и веса по умолчанию."""

from config import genre_tags
from config import scheme
from config import tags_work

DATA_DIR = 'C:/DATA/movies-learn/'
FILE_NAME = 'C:/DATA/movies-learn/dataset.json'
WEIGHTS_JSON = 'C:/DATA/movies-learn/weights.json'
CRITERIA_POOL_JSON = 'C:/DATA/movies-learn/candidate_criteria.json'
CANDIDATE_POOL_JSON = 'C:/DATA/movies-learn/candidate_pool.json'
MODEL_METRICS_JSON = 'config/model_metrics.json'
API_LOG_FILE = 'C:/DATA/movies-learn/api_requests.log'
BACKUP_DIR = 'C:/BACKUP/movies-learn/BACKUP/'

DIR_META = 'C:/META/meta-movies-learn/'
META_JSON = 'C:/META/meta-movies-learn/meta_data.json'

DIR_TXT = 'C:/TXT_FILES/movies-learn/'
EDIT_EXCEL = 'C:/TXT_FILES/movies-learn/edit_dataset.xlsx'

MAIN_INFO = []
RAW_SCORES = []
TAGS_VIBE = []
GENRE = []
TAGS_VIBE_SECTION = scheme.TAGS_VIBE
GENRE_SECTION = scheme.GENRE
BIAS_FEATURE = "bias"

COMPUTED_SCORES = []

CSV_FIELDS = []
FEATURES = []
RAW_META_FIELDS = []
FEATURES_CONST = []

SECTION_LABELS = {
    scheme.MAIN_INFO: "Основная информация",
    scheme.RAW_SCORES: "Исходные данные",
    scheme.TAGS_VIBE: "Теги вайба",
    scheme.GENRE: "Жанровая разметка",
}

FIELD_LABELS = {
    "title": "Название",
    "user_score": "Ваша оценка",
    "year": "Год выхода",
    BIAS_FEATURE: "Свободный член",
    "kp_score": "Рейтинг Кинопоиска",
    "kp_votes": "Количество голосов Кинопоиска",
    "imdb_score": "Рейтинг IMDb",
    "imdb_votes": "Количество голосов IMDb",
    "kp_popularity": "Популярность Кинопоиска",
    "imdb_popularity": "Популярность IMDb",
}

TAG_RULES = {}

TRANSLATION = {
    "features": {
        BIAS_FEATURE: "Bias",
        "kp_score": "Kinopoisk score",
        "kp_popularity": "Kinopoisk popularity",
        "imdb_score": "IMDb score",
        "imdb_popularity": "IMDb popularity",
    },
    "meta features": {
        "year": "Year",
        "kp_score": "Kinopoisk score",
        "kp_votes": "Kinopoisk votes",
        "imdb_score": "IMDb score",
        "imdb_votes": "IMDb votes",
    },
}


def refresh_dynamic_fields() -> None:
    """Обновляет динамические списки признаков и связанные справочники."""
    global MAIN_INFO, RAW_SCORES, TAGS_VIBE, GENRE
    global COMPUTED_SCORES, CSV_FIELDS, FEATURES, RAW_META_FIELDS, FEATURES_CONST
    global ONLY_SCORES, TAG_RULES, DEFAULT_WEIGHTS, FIELD_LABELS

    MAIN_INFO = scheme.get_fields(scheme.MAIN_INFO)
    RAW_SCORES = scheme.get_fields(scheme.RAW_SCORES)
    TAGS_VIBE = scheme.get_fields(scheme.TAGS_VIBE)
    GENRE = scheme.get_fields(scheme.GENRE)
    COMPUTED_SCORES = scheme.get_computed_fields()

    CSV_FIELDS = MAIN_INFO + RAW_SCORES + TAGS_VIBE + GENRE
    FEATURES = [BIAS_FEATURE] + COMPUTED_SCORES + TAGS_VIBE + GENRE
    RAW_META_FIELDS = RAW_SCORES
    FEATURES_CONST = COMPUTED_SCORES

    ONLY_SCORES = CSV_FIELDS.copy()
    ONLY_SCORES.remove("title")
    ONLY_SCORES.remove("year")

    FIELD_LABELS = {
        "title": "Название",
        "user_score": "Ваша оценка",
        "year": "Год выхода",
        BIAS_FEATURE: "Свободный член",
        "kp_score": "Рейтинг Кинопоиска",
        "kp_votes": "Количество голосов Кинопоиска",
        "imdb_score": "Рейтинг IMDb",
        "imdb_votes": "Количество голосов IMDb",
        "kp_popularity": "Популярность Кинопоиска",
        "imdb_popularity": "Популярность IMDb",
    }
    FIELD_LABELS.update(tags_work.get_tag_labels())
    FIELD_LABELS.update(genre_tags.get_genre_labels())

    TAG_RULES = tags_work.get_tag_rules()

    if len(FEATURES) == 0:
        DEFAULT_WEIGHTS = {}
    else:
        DEFAULT_WEIGHTS = {
            feature: round(1 / len(FEATURES), 4)
            for feature in FEATURES
        }

    TRANSLATION["features"] = {
        BIAS_FEATURE: "Bias",
        "kp_score": "Kinopoisk score",
        "kp_popularity": "Kinopoisk popularity",
        "imdb_score": "IMDb score",
        "imdb_popularity": "IMDb popularity",
    }
    TRANSLATION["features"].update(tags_work.get_tag_translations())
    TRANSLATION["features"].update(genre_tags.get_genre_translations())


refresh_dynamic_fields()

COMMANDS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]
BAD_CHARACTERS = ",.'][@#$%^&*()?"
THRESHOLD = 6.5
NOW_YEAR = 2026
