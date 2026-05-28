import scheme

DATA_DIR = 'C:/DATA/movies-learn/'
FILE_NAME = 'C:/DATA/movies-learn/dataset.json'
WEIGHTS_JSON = 'C:/DATA/movies-learn/weights.json'
BACKUP_DIR = 'C:/BACKUP/movies-learn/BACKUP/'


DIR_META = 'C:/META/meta-movies-learn/'
META_JSON = 'C:/META/meta-movies-learn/meta_data.json'

DIR_TXT = 'C:/TXT_FILES/movies-learn/'
TXT_INPUT = 'C:/TXT_FILES/movies-learn/input.txt'
CSV_INPUT = 'C:/TXT_FILES/movies-learn/input.csv'
EDIT_CSV = 'C:/TXT_FILES/movies-learn/edit_dataset.csv'



MAIN_INFO = scheme.get_fields(scheme.MAIN_INFO)
RAW_SCORES = scheme.get_fields(scheme.RAW_SCORES)
TAGS_VIBE = scheme.get_fields(scheme.TAGS_VIBE)
TAGS_VIBE_SECTION = scheme.TAGS_VIBE

COMPUTED_SCORES = scheme.get_computed_fields()

CSV_FIELDS = MAIN_INFO + RAW_SCORES + TAGS_VIBE
FEATURES = COMPUTED_SCORES + TAGS_VIBE
RAW_META_FIELDS = RAW_SCORES
FEATURES_CONST = COMPUTED_SCORES

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
    "imdb_popularity": "Популярность IMDb",
    "has_crime": "Есть криминал",
    "has_psyhology": "Есть психология",
    "has_comedy": "Есть комедия",
    "has_mystic": "Есть мистика",
    "has_romantic_tension": "Любовный трегольник"
}

TAG_RULES = {
    "has_crime": {
        "title": "Криминал",
        "question": "Есть ли в основе истории преступление, расследование, мафия, афера или криминальная среда?",
        "scale": [
            "0: нет или почти нет",
            "1: да, криминал заметно влияет на историю"
        ]
    },
    "has_psyhology": {
        "title": "Психология",
        "question": "Есть ли заметный фокус на мотивах, травмах, манипуляциях, внутреннем конфликте или поведении людей?",
        "scale": [
            "0: нет, психология не является важной частью просмотра",
            "1: да, психологический слой важен"
        ]
    },
    "has_comedy": {
        "title": "Комедия",
        "question": "Есть ли в проекте регулярная комедийная подача или юмор как важная часть тона?",
        "scale": [
            "0: нет, юмор редкий или случайный",
            "1: да, комедия заметно влияет на тон"
        ]
    },
    "has_mystic": {
        "title": "Мистика",
        "question": "Есть ли сверхъестественное, мистическая загадка, необъяснимые явления или ощущение потустороннего?",
        "scale": [
            "0: нет мистического слоя",
            "1: да, мистика заметна"
        ]
    },
    "has_romantic_tension": {
        "title": "Романтическое напряжение",
        "question": "Есть ли один персонаж добивается другого, есть отказы, ревность, притяжение, ожидание сближения или любовный треугольник?",
        "scale": [
            "0: нет, романтика отсутствует или не влияет на основной интерес",
            "1: да, романтическое напряжение заметно влияет на сюжет или вовлечение"]
}
    

}

DEFAULT_WEIGHTS = {
    feature: round(1 / len(FEATURES), 4)
    for feature in FEATURES
}

TRANSLATION = {
    'features': {
        "kp_score": "Kinopoisk score",
        "kp_popularity": "Kinopoisk popularity",
        "imdb_score": "IMDb score",
        "imdb_popularity": "IMDb popularity",
        "has_crime": "Crime tag",
        "has_psyhology": "Psychology tag",
        "has_comedy": "Comedy tag",
        "has_mystic": "Mystic tag",
        "has_romantic_tension": "Romantic tension tag" 
    },
    'meta features': {
        "year": "Year",
        "kp_score": "Kinopoisk score",
        "kp_votes": "Kinopoisk votes",
        "imdb_score": "IMDb score",
        "imdb_votes": "IMDb votes"
    }
}

COMMANDS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]
BAD_CHARACTERS = ",.'][@#$%^&*()?"
THRESHOLD = 6.5
NOW_YEAR = 2026
STEP = 0.01
