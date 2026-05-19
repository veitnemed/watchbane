import json
import os
import valid

DATA_DIR = 'C:/series-learn'
FILE_NAME = 'C:/series-learn/dataset.json'

DIR_FEARURES = 'C:/series-learn'
FILE_FITURES = 'C:/series-learn/features.json'

KEYS = ['title','liked', 'user_score', 'features']
FEATURES = ["kp_score","kp_amount","hook", "holding", "tension"]

THRESHOLD = 6.5
DELTA = 2.5

def is_json_exists(file_name):
    return os.path.exists(file_name)

def init_dataset():
    empty_list = []

    if is_json_exists(FILE_NAME) is False:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(FILE_NAME, 'w', encoding='UTF-8') as file:
            json.dump(empty_list, file, ensure_ascii=False, indent=4)

def load_dataset() -> list:
    '''Возвращает список json-объектов'''

    with open(FILE_NAME, 'r', encoding='UTF-8') as file:
        return json.load(file)

def save_dataset(data: list):
    '''Перезаписываем новый список в json'''
    
    with open(FILE_NAME, 'w', encoding='UTF-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def add_series(title: str, user_score: float, features: dict) -> bool:
    ''' Добавляем ещё один объект в json'''
    
    if valid.is_valid_features(features) is False:
        print('Ошибка добавления! Не хватает параметров')
        return False
    if valid.is_valid_grade(list(features.values())) is False:
        print('Ошибка добавления! Неверное значение параметров')
        return False
    if valid.is_valid_grade(user_score) is False:
        print('Ошибка добавления! Некорректное значение user_score')
        return False

    data = load_dataset()
    new_obj = {}
    
    new_obj['title'] = title
    new_obj['user_score'] = user_score
    new_obj['liked'] = 1 if user_score >= THRESHOLD  else 0
    new_obj['features'] = features

    data.append(new_obj)
    save_dataset(data)
    return True

def is_origin_title(new_title: str) -> bool:
    data = load_dataset()
    
    for d in data:
        if d['title'] == new_title:
            return False
    return True



    
    