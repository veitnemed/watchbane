import storage
import ui
import valid


def ask_object():
        
        list_features = storage.load_list_fetures()
        
        title = input('Введите название: ')
        
        user_score = float(input('Оценка по общему впечатлению: '))
        
        new_dict = {}
        for features in list_features:
            answer = input(f'{features} >> ')
            if valid.is_parse_str_float(answer):
                new_dict[features] = float(answer)
            else:
                print('Неверный тип данных!')
            

        res = storage.add_series(title, user_score, new_dict)
        
        if res is False:
            print('Ошибка! Новый объект не добавлен')
        else:
            print('Новый объект добавлен!')
        print('Количество сериалов: ', len(storage.load_dataset())) 
        
def main_loop():
    
    storage.init_dataset()
    while True:
        ui.clean_terminal()
        ui.show_main_menu()
        n = input('>> ')
        if n == '0':
            break
        elif n == '1':
            ask_object()
        elif n == '2':
            print('Количество записей:', len(storage.load_dataset()))
        else:
            print('Неизвестная команда')
        input('Enter, чтобы продолжить...')
        
    
    

if __name__ == "__main__":

    main_loop()
    