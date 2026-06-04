"""Хранит общие функции меню и параметры обучения."""

from config import constant
from model_work import model
from interface import request
from data_work import storage
from core import valid


TRAIN_STEP = constant.STEP
TRAIN_PLATEAU_SCORE = 500


def press_enter():
    """Ждет нажатия Enter."""
    input('Enter, чтобы продолжить >>')


def get_menu_state():
    """Собирает состояние для меню."""
    data = storage.load_dataset()
    weights = storage.load_weights()
    movies_counter = len(data)
    abs_error = model.mean_absolute_error(data, weights)
    return data, weights, movies_counter, abs_error


def setup_train_params():
    """Настраивает параметры обучения."""
    global TRAIN_STEP, TRAIN_PLATEAU_SCORE

    step = request.loop_input(
        text=f'Шаг обучения [{TRAIN_STEP}] >> ',
        funcs_list=[valid.is_correct_train_step]
    )
    plateau_score = request.loop_input(
        text=f'Попыток без улучшения для плато [{TRAIN_PLATEAU_SCORE}] >> ',
        funcs_list=[valid.is_correct_plateau_score]
    )

    if step.strip() != "":
        TRAIN_STEP = valid.parse_float(step)
    if plateau_score.strip() != "":
        TRAIN_PLATEAU_SCORE = int(plateau_score)
    print(f'Параметры обучения обновлены: шаг={TRAIN_STEP}, плато={TRAIN_PLATEAU_SCORE}')
