"""Хранит и настраивает параметры запуска обучения из меню."""

from config import constant
from core import valid
from interface import request

TRAIN_STEP = constant.STEP
TRAIN_PLATEAU_SCORE = 500


def setup_train_params():
    """Запрашивает и обновляет шаг обучения и лимит попыток без улучшения."""
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
