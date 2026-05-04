import storage


FILE_NAME = 'thesaurus.json'
def correct_word(word: str) -> bool:
    
    return len(word.strip()) > 1


def ask_new_item() -> tuple:
    while True:
        termin = input('Введите термин: ')
        if correct_word(termin) is True:
            break
        print('Некорректный ввод')
    while True:
        definition = input('Введите определение: ')
        if correct_word(definition) is True:
            break
        print('Некорректный ввод')
    return (termin, definition)



    
def main_cy():
    storage.create_json(FILE_NAME)
    termin, definition = ask_new_item()
    is_add = storage.add_term(FILE_NAME, termin, definition)
    if is_add:
        print('Термин добавлен!')
    else:
        print('Термин не добавлен!')

    

if __name__ == "__main__":
    main_cy()