"""Собирает константы проекта: пути, поля и подписи."""

from config import scheme
from config.app_paths import get_app_paths

_APP_PATHS = get_app_paths()

APP_DATA_DIR = str(_APP_PATHS.data_dir)
WATCHED_DIR = str(_APP_PATHS.watched_dir)
CANDIDATES_DIR = str(_APP_PATHS.candidates_dir)
CACHE_DIR = str(_APP_PATHS.cache_dir)
POSTERS_DIR = str(_APP_PATHS.posters_dir)
EXPORTS_DIR = str(_APP_PATHS.exports_dir)
LOGS_DIR = str(_APP_PATHS.logs_dir)
CONFIG_DIR = str(_APP_PATHS.config_dir)

DATA_DIR = WATCHED_DIR
API_LOG_FILE = str(_APP_PATHS.logs_dir / "api_requests.log")
BACKUP_DIR = str(_APP_PATHS.backups_dir) + "/"

DIR_META = WATCHED_DIR

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
