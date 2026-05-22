import json
import os
import valid
import constant
from datetime import datetime

def is_json_exists(file_name):
    return os.path.exists(file_name)

def init_dataset():
    empty_list = []

    if is_json_exists(constant.FILE_NAME) is False:
        os.makedirs(constant.DATA_DIR, exist_ok=True)
        with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
            json.dump(empty_list, file, ensure_ascii=False, indent=4)

def init_meta():
    empty_dict = {}

    if is_json_exists(constant.META_JSON) is False:
        os.makedirs(constant.DIR_META, exist_ok=True)
        with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
            json.dump(empty_dict, file, ensure_ascii=False, indent=4)
    
def load_meta() -> dict:
    
    with open(constant.META_JSON, 'r', encoding='UTF-8') as file:
        return json.load(file)

def save_meta(meta: dict):
    with open(constant.META_JSON, 'w', encoding='UTF-8') as file:
        json.dump(meta, file, ensure_ascii=False, indent=4)
    
def load_dataset() -> list:
    '''Возвращает список dict-объектов'''

    with open(constant.FILE_NAME, 'r', encoding='UTF-8') as file:
        return json.load(file)

def save_dataset(data: list):
    '''Перезаписываем новый список в json'''
    with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def is_origin_title(new_title: str) -> bool:
    
    data = load_dataset()
    
    for d in data:
        if d['title'].strip().lower() == new_title.strip().lower():
            return False
    return True
def add_movies_to_meta(title, user_score, features_const):
    title = title.strip()
    meta = load_meta()
    if valid.is_correct_title(title) is False:
        print('Ошибка добавления! Некорректное название')
        return False
    
    
    
    if valid.is_valid_features_meta(features_const) is False:
        print('Ошибка добавления! Не хватает параметров')
        return False
    if valid.is_correct_score(user_score) is False:
        print('Ошибка добавления! Некорректное значение user_score')
        return False
    
    if valid.is_valid_grade(list(features_const.values())) is False:
        print('Ошибка добавления! Неверное значение параметров')
        return False
    
    user_score_float = float(user_score)
    meta[title] = {
    'user_score': user_score_float,
    'features_const': features_const
                }
    save_meta(meta)
    return True
    
def add_movies(title: str, user_score: str, features: dict) -> bool:
    ''' Добавляем ещё один объект в json'''
    
    meta = load_meta()
    title = title.strip()
    if valid.is_correct_title(title) is False:
        print('Ошибка добавления! Некорректное название')
        return False
    if is_origin_title(title) is False:
        print('Ошибка добавления! Такой объект добавлен')
        return False
    
    if valid.is_valid_features(features) is False:
        print('Ошибка добавления! Не хватает параметров')
        return False
    
    if valid.is_valid_grade(list(features.values())) is False:
        print('Ошибка добавления! Неверное значение параметров')
        return False
    
    if valid.is_correct_score(user_score) is False:
        print('Ошибка добавления! Некорректное значение user_score')
        return False
    
    new_obj = {}
    new_obj['features'] = features

    data = load_dataset()
    user_score_float = float(user_score)
    new_obj['title'] = title
    new_obj['user_score'] = user_score_float
    
    if title in meta:
        new_obj['user_score'] = meta[title]['user_score']
        for k, v in meta[title]['features_const'].items():
            new_obj['features'][k] = v
    
    data.append(new_obj)
    save_dataset(data)
    return True

def clean_dataset():
    empty_list = []
    with open(constant.FILE_NAME, 'w', encoding='UTF-8') as file:
        json.dump(empty_list, file, ensure_ascii=False, indent=4)
        
def init_weights():
    if is_json_exists(constant.WEIGHTS_JSON) is False:
        with open(constant.WEIGHTS_JSON, 'w', encoding='UTF-8') as file:
            json.dump(constant.DEFAULT_WEIGHTS, file, ensure_ascii=False, indent=4)

def load_weights() -> list:
    with open(constant.WEIGHTS_JSON, 'r', encoding='UTF-8') as file:
        return json.load(file)
   
def save_weights(data: dict):
    with open(constant.WEIGHTS_JSON, 'w', encoding='UTF-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)  

def uppdate_weights(weights: dict):
    save_weights(weights)
    
def init_txt():

    if is_json_exists(constant.TXT_INPUT) is False:
        with open(constant.TXT_INPUT, 'w', encoding='UTF-8') as file:
            return

def input_txt() -> bool:
    '''Импорт записей из txt в dataset.json'''
    
    expected_len = len(constant.FEATURES) + 2
    added_count = 0
    with open(constant.TXT_INPUT, 'r', encoding='utf-8-sig') as f: 
        data = f.readlines()
        
        if len(data) == 0:
            print('Текстовый файл пуст!')
            return False
        
    for idx, line in enumerate(data):
        if line.strip() == "":
            continue
        param = line.strip().split(';')
        
        param = [p.strip() for p in line.strip().split(';')]
        
        if len(param) != expected_len:
            print(f'Ошибка парсинга из текстового файла! Строка {idx+1}')
            return False
        
        if param[0].strip().lower() == 'title':
            continue
        
        title = param[0]
        if valid.is_correct_title(title) is False:
            print(f'Строка {idx+1}: Некорректное имя!')
            return False
        
        if is_origin_title(title) is False:
            print(f'Строка {idx+1}: Такое имя уже есть')
            return False
        
        if valid.is_correct_score(param[1]) is False:
            print(f'Строка {idx+1}: Некорректное значения параметров')
            return False
        
        user_score = float(param[1])  
        features_dict = {}   
        for i, value in enumerate(param[2:]):
            if valid.is_correct_score(value) is False:
                print(f'Строка {idx+1}: Некорректное значения параметров')
                return False
            features_dict[constant.FEATURES[i]] = float(value)
              
        result = add_movies(
            title=title,
            user_score=user_score,
        features=features_dict
        )
        if result is False:
            print(f'Ошибка парсинга! Строка {idx+1}')
            return False
        added_count += 1        
    
    if added_count == 0:
        print('Нет строк для импорта')
        return False
    
    print(f'Импорт завершён. Добавлено записей: {added_count}')
    return True 

def restart_txt():
    with open(constant.TXT_INPUT, 'w', encoding='UTF-8') as file:
            return


def create_backup():
    
    dataset = load_dataset()
    date_name = datetime.now().strftime('%d-%m-%Y %H-%M-%S')
    b = constant.BACKUP_DIR + date_name + '.json'
    if is_json_exists(b) is False:
        os.makedirs(constant.BACKUP_DIR, exist_ok=True)
    
    with open(b, 'w', encoding='UTF-8') as file:
        json.dump(dataset, file, ensure_ascii=False, indent=4)


