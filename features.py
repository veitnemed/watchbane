      
def init_defoult_features():

    if is_json_exists(FILE_FITURES) is False:
        os.makedirs(DIR_FEARURES, exist_ok=True)
        with open(FILE_FITURES, 'w', encoding='UTF-8') as file:
            json.dump(DEFOULT_FEATURES, file, ensure_ascii=False, indent=4)

def load_list_fetures() -> list:
    '''Возвращает список json-объектов'''

    with open(FILE_FITURES, 'r', encoding='UTF-8') as file:
        return json.load(file)

def save_list_fetures(data: list):
    '''Перезаписываем новый список в json'''
    
    with open(FILE_FITURES, 'w', encoding='UTF-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def add_new_features(new_features: str):
    
    data = load_dataset()
    
    for obj in data:
        obj['features'][new_features] = None
        
    features_list = load_list_fetures()
    features_list.append(new_features)
    save_list_fetures(features_list)
    
