import storage

FEATURE_NAMES = ["hook", "holding", "tension"]
BAD_CHARACTERS = ",.'][@#$%^&*()?"

def is_valid_features(features: dict) -> bool:
    '''Проверка корректности ключей словаря features'''
    return set(FEATURE_NAMES) & set(features.keys()) == set(FEATURE_NAMES)


 
def is_valid_grade(nums: list, max_value = 10) -> bool:
    '''Проверка числа от 0 до max_value'''
    
    if isinstance(nums,list):
        for n in nums:
            if isinstance(n,(int,float)) is False:
                return False
            if n < 0 or n > max_value:
                return False
        return True
    
    if isinstance(nums,(int,float)):
        return 0 <= nums <= max_value
    return False

def is_origin_title(new_title: str) -> bool:
    new_title = new_title.strip()
    data = storage.load_dataset()
    
    for d in data:
        if d['title'] == new_title:
            return False
    return True       
        
def is_correct_title(title):
    title = title.strip()
    if title == '':
        return False
    return set(BAD_CHARACTERS) & set(title) == 0

def is_parse_str_float(a):
    
    try:
        float(a)
        return True
    except ValueError:
        return False
