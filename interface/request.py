"""Запрашивает данные у пользователя и собирает объект фильма."""

from data_work import storage
from core import valid
from config import scheme
import copy
from config import constant

FUNCS = copy.deepcopy(scheme.SHEME_ADD)
FUNCS.pop("computed_scores", None)

def get_validators(tags_validators: list, max_value: int = 1) -> list:
    """Собирает валидаторы для поля схемы."""
    validators = []
    for tag in tags_validators:
        if tag == "tags_score":
            validators.append(lambda value, max_value=max_value: valid.is_tags_score(value, max_value))
        else:
            validators.append(valid.VALIDATORS[tag])
    return validators
    

def get_label(feature: str) -> str:
    """Возвращает подпись поля."""
    return constant.FIELD_LABELS.get(feature, feature)


def get_section_label(section_name: str) -> str:
    """Возвращает подпись секции."""
    return constant.SECTION_LABELS.get(section_name, section_name)


def loop_input(text, funcs_list):
    """Запрашивает ввод до прохождения проверок."""
    
    while True:
        value = input(text)
        for func in funcs_list:
            if func(value) is False:
                break
        else:
            break      
    return value


def show_score_help(feature: str) -> None:
    """Показывает подсказку по шкале тега."""
    help_info = constant.TAG_RULES.get(feature)
    if help_info is None:
        return

    print("\n" + "-" * 40)
    print(help_info["title"])
    print(help_info["question"])
    print("Шкала оценки:")
    for line in help_info["scale"]:
        print(f"  {line}")

def request_all_scores() -> dict:
    """Запрашивает все данные фильма."""
    movie = {}

    for section_name, section_fields in FUNCS.items():
        section = {}

        print(f'\n--- {get_section_label(section_name)} ---')

        for feature, field_settings in section_fields.items():
            if section_name == scheme.TAGS_VIBE:
                show_score_help(feature)

            tags_validators = field_settings["tag"]
            type_func = field_settings["type"]
            funcs = get_validators(tags_validators, field_settings.get("max_value", 1))
            answer = loop_input(
                text=f'>> {get_label(feature)}: ',
                funcs_list=funcs
                            )
            if type_func is float:
                section[feature] = valid.parse_float(answer)
            else:
                section[feature] = type_func(answer)

        movie[section_name] = section

    return movie
