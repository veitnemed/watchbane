"""Собирает константы проекта: пути, поля и подписи."""

from config import scheme

APP_DATA_DIR = 'data'
WATCHED_DIR = 'data/watched'
CANDIDATES_DIR = 'data/candidates'
CACHE_DIR = 'data/cache'
EXPORTS_DIR = 'data/exports'
LOGS_DIR = 'data/logs'

DATA_DIR = WATCHED_DIR

# Legacy JSON paths (import/export/migrations only; SQLite is runtime storage).
FILE_NAME = WATCHED_DIR + '/titles.json'
CRITERIA_POOL_JSON = CANDIDATES_DIR + '/criteria.json'
CANDIDATE_POOL_JSON = CANDIDATES_DIR + '/pool.json'
API_LOG_FILE = LOGS_DIR + '/api_requests.log'
BACKUP_DIR = 'data/backups/'

DIR_META = WATCHED_DIR
META_JSON = WATCHED_DIR + '/meta.json'

# Legacy alias kept for archive scripts that write reports under exports/.
DIR_TXT = EXPORTS_DIR

# Dynamic field lists — populated at import via refresh_dynamic_fields().
MAIN_INFO: list
RAW_SCORES: list
COMPUTED_SCORES: list
CSV_FIELDS: list
FEATURES: list
RAW_META_FIELDS: list
FEATURES_CONST: list
ONLY_SCORES: list

SECTION_LABELS = {
    scheme.MAIN_INFO: "Основная информация",
    scheme.RAW_SCORES: "Исходные данные",
}

FIELD_LABELS = {
    "title": "Название",
    "user_score": "Ваша оценка",
    "year": "Год выхода",
    "tmdb_score": "Рейтинг TMDb",
    "tmdb_votes": "Голоса TMDb",
    "tmdb_popularity": "Популярность TMDb",
}

TAG_RULES: dict

TRANSLATION = {
    "features": {
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
    global MAIN_INFO, RAW_SCORES
    global COMPUTED_SCORES, CSV_FIELDS, FEATURES, RAW_META_FIELDS, FEATURES_CONST
    global ONLY_SCORES, TAG_RULES, FIELD_LABELS

    MAIN_INFO = scheme.get_fields(scheme.MAIN_INFO)
    RAW_SCORES = scheme.get_fields(scheme.RAW_SCORES)
    COMPUTED_SCORES = scheme.get_computed_fields()

    CSV_FIELDS = MAIN_INFO + RAW_SCORES
    FEATURES = list(COMPUTED_SCORES)
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
        "tmdb_score": "Рейтинг TMDb",
        "tmdb_votes": "Голоса TMDb",
        "tmdb_popularity": "Популярность TMDb",
    }

    TAG_RULES = {}

    TRANSLATION["features"] = {
        "tmdb_score": "TMDb score",
        "tmdb_votes": "TMDb votes",
        "tmdb_popularity": "TMDb popularity",
    }
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
