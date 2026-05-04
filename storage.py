import json 
import os

FILE_NAME = 'thesaurus.json'

def json_exists(file_name):
    return os.path.exists(file_name)

def create_json(file_name):
    d = {}
    if json_exists(file_name) is False:
        with open(file_name, 'w', encoding='UTF-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=4)

def load_json(file_name: str) -> dict:
    '''Возвращает словарь json-файла'''

    with open(file_name, 'r', encoding='UTF-8') as f:
        return json.load(f)

def save_json(file_name: str, data_dict: dict):
    with open(file_name, 'w', encoding='UTF-8') as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=4)

def term_exists(file_name: str, term: str) -> bool:
    term = term.strip()
    return term in load_json(file_name)

def add_term(file_name: str, term: str, definition: str) -> bool:
    data = load_json(file_name)
    term = term.strip()
    definition = definition.strip()
    if term == '' or definition == '':
        return False
    if term_exists(file_name, term):
        return False
    
    data[term] = definition
    save_json(file_name, data)
    return True



def get_term(file_name: str, term: str):
    data = load_json(file_name)
    term = term.strip()
    if term in data:
        return data[term]
    return None

def list_terms(file_name: str) -> list:
    return list(load_json(file_name).keys())

def delete_term(file_name: str, term: str) -> bool:
    '''Удаляем пару из словаря'''

    term = term.strip()
    data = load_json(file_name)
    if term in data:
        del data[term]
        save_json(file_name, data)
        return True
    return False






