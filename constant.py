DATA_DIR = 'C:/movies-learn'
FILE_NAME = 'C:/movies-learn/dataset.json'
WEIGHTS_JSON = 'C:/movies-learn/weights.json'
BACKUP_DIR = 'C:/backup-movies-learn/'
DIR_META = 'C:/meta-movies-learn/'
META_JSON = 'C:/meta-movies-learn/meta_data.json'
TXT_INPUT = 'C:/movies-learn/input.txt'


OBJECTIVE_FEATURES = ["kp_score", "imdb_votes", "last_episode_score","delta_score"]
LLM_FEATURES = ["hook", "holding", "tension"]
FEATURES = OBJECTIVE_FEATURES + LLM_FEATURES
FEATURES_CONST = OBJECTIVE_FEATURES

DEFAULT_WEIGHTS = {
    feature: round(1 / len(FEATURES), 4)
    for feature in FEATURES
}
FEATURES_RUSSIAN = {
            "kp_score": "Рейтинг кинопоиска",
            "hook": "Сюжетная завязка",
            "holding": ""
}

COMMANDS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9","10"]
BAD_CHARACTERS = ",.'][@#$%^&*()?"
THRESHOLD = 6.5



STEP = 0.01

