"""Собирает константы проекта: пути, поля и подписи."""

from config import genre_tags
from config import scheme
from config import tags_work

APP_DATA_DIR = 'data'
WATCHED_DIR = 'data/watched'
CANDIDATES_DIR = 'data/candidates'
CACHE_DIR = 'data/cache'
EXPORTS_DIR = 'data/exports'
LOGS_DIR = 'data/logs'
APP_SETTINGS_JSON = APP_DATA_DIR + '/settings.json'

DATA_DIR = WATCHED_DIR
FILE_NAME = WATCHED_DIR + '/titles.json'
CRITERIA_POOL_JSON = CANDIDATES_DIR + '/criteria.json'
CANDIDATE_POOL_JSON = CANDIDATES_DIR + '/pool.json'
API_LOG_FILE = LOGS_DIR + '/api_requests.log'
BACKUP_DIR = 'data/backups/'

DIR_META = WATCHED_DIR
META_JSON = WATCHED_DIR + '/meta.json'

DIR_TXT = EXPORTS_DIR
EDIT_EXCEL = EXPORTS_DIR + '/edit_dataset.xlsx'

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
    "tmdb_score": "Рейтинг TMDb",
    "tmdb_votes": "Голоса TMDb",
    "tmdb_popularity": "Популярность TMDb",
}

TAG_RULES = {}

TRANSLATION = {
    "features": {
        BIAS_FEATURE: "Bias",
        "tmdb_score": "TMDb score",
        "tmdb_votes": "TMDb votes",
        "tmdb_popularity": "TMDb popularity",
    },
    "meta features": {
        "year": "Year",
        "tmdb_score": "TMDb score",
        "tmdb_votes": "TMDb votes",
        "tmdb_popularity": "TMDb popularity",
    },
}


def refresh_dynamic_fields() -> None:
    """Обновляет динамические списки признаков и связанные справочники."""
    global MAIN_INFO, RAW_SCORES, TAGS_VIBE, GENRE
    global COMPUTED_SCORES, CSV_FIELDS, FEATURES, RAW_META_FIELDS, FEATURES_CONST
    global ONLY_SCORES, TAG_RULES, FIELD_LABELS

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
    ONLY_SCORES.remove("country")

    FIELD_LABELS = {
        "title": "Название",
        "user_score": "Ваша оценка",
        "year": "Год выхода",
        BIAS_FEATURE: "Свободный член",
        "tmdb_score": "Рейтинг TMDb",
        "tmdb_votes": "Голоса TMDb",
        "tmdb_popularity": "Популярность TMDb",
    }
    FIELD_LABELS.update(tags_work.get_tag_labels())
    FIELD_LABELS.update(genre_tags.get_genre_labels())

    TAG_RULES = tags_work.get_tag_rules()

    TRANSLATION["features"] = {
        BIAS_FEATURE: "Bias",
        "tmdb_score": "TMDb score",
        "tmdb_votes": "TMDb votes",
        "tmdb_popularity": "TMDb popularity",
    }
    TRANSLATION["features"].update(tags_work.get_tag_translations())
    TRANSLATION["features"].update(genre_tags.get_genre_translations())
    TRANSLATION["meta features"] = {
        "year": "Year",
        "tmdb_score": "TMDb score",
        "tmdb_votes": "TMDb votes",
        "tmdb_popularity": "TMDb popularity",
    }


refresh_dynamic_fields()

COMMANDS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]
BAD_CHARACTERS = ",.'][@#$%^&*()?"
THRESHOLD = 6.5
NOW_YEAR = 2026
