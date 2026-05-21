DATA_DIR = 'C:/movies-learn'
FILE_NAME = 'C:/movies-learn/dataset.json'
WEIGHTS_JSON = 'C:/movies-learn/weights.json'
TXT_INPUT = 'C:/movies-learn/input.txt'


FEATURES = ["kp_score", "hook", "holding", "tension"]
FEATURES_RUSSIAN = {
            "kp_score": "Рейтинг кинопоиска",
            "hook": "Сюжетная завязка",
            "holding": ""
}

COMMANDS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
BAD_CHARACTERS = ",.'][@#$%^&*()?"
THRESHOLD = 6.5

DEFAULT_WEIGHTS = {
    "kp_score": 0.25,
    "hook": 0.25,
    "holding": 0.25,
    "tension": 0.25
}

STEP = 0.01

