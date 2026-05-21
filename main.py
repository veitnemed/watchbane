import storage
import ui
import valid
import constant
import model
import time


    

def show_all_movies():
    data = storage.load_dataset()
    if len(data) == 0:
        print('Датасет пуст!')
        return
    
    for idx, obj in enumerate(data):
        title = obj['title']
        user_score = obj['user_score']
        print(f"{idx+1}) {title} | оценка: {user_score}")


def loop_input(text: str, funcs_list: list):
    while True:
        w = input(text)

        for f in funcs_list:
            if f(w) is False:
                print('Некорректный ввод')
                break
        else:
            return w
   
def get_predict(weights):
    title = loop_input(
        text='Введите название: ',
        funcs_list=[valid.is_correct_title])
    
    features = {}
    for feature in constant.FEATURES:   
        answer = loop_input(
            text=f'{feature} >> ',
            funcs_list=[valid.is_correct_score]
        )
        features[feature] = float(answer)
    score = model.predict_score(features, weights)
    
    print(f'Оценка модели для {title}: {score}')
     
    
          
def ask_object():   
    title = loop_input(
        text='Введите название: ',
        funcs_list=[valid.is_correct_title, storage.is_origin_title]
    )

    user_score = loop_input(
        text='Оценка по общему впечатлению: ',
        funcs_list=[valid.is_correct_score]
    )

    new_dict = {}

    for feature in constant.FEATURES:   
        answer = loop_input(
            text=f'{feature} >> ',
            funcs_list=[valid.is_correct_score]
        )
        new_dict[feature] = float(answer)

    result = storage.add_movies(
        title=title,
        user_score=user_score,
        features=new_dict
    )

    if result:
        print('Новая запись добавлена!')
    else:
        print('Ошибка! Новая запись не добавлена')

def train_model(data, weights):
    start_time = time.perf_counter()
    old_error = model.mean_absolute_error(data, weights)
    new_weights = model.selection_weights(data, weights)
    storage.save_weights(new_weights)
    new_error = model.mean_absolute_error(data, new_weights)
            
    print('Новые веса: \n')
    for weight, value in new_weights.items():
        print(f'{weight}: {round(value,2)}')
                
    print('\nОшибка до обучения: ', round(old_error,2))
    print('Ошибка после обучения: ', round(new_error,2))
    end_time = time.perf_counter()
    print(f'\nВремя подбора весов: {round(end_time-start_time,4)} сек.')  

def show_feature_importance(data: list):
    '''Вычилсяем ошибку без каждого параметра'''
    
    data = storage.load_dataset()
    for feature in constant.FEATURES:
        weights_without_holding = model.selection_weights_without_feature(data,excluded_feature=feature)
        error_without_holding = model.mean_absolute_error(data, weights_without_holding)
        print(f"\nВеса без {feature}:")
        for weight, value in weights_without_holding.items():
            print(f"{weight}: {round(value, 2)}")

            print(f"Ошибка без {feature}:", round(error_without_holding,4))

def main_loop():
    
    storage.init_dataset()
    storage.init_weights()
    storage.init_txt()
    
    while True:
        ui.clean_terminal()
        data = storage.load_dataset()
        weights = storage.load_weights()
        movies_counter = len(data)
        ui.show_main_menu(movies_counter)
        
        command = loop_input(text=">> ", funcs_list=[valid.is_correct_main_menu_command])
        if command == '0':
            break
        elif command == '1':
            ui.clean_terminal()
            ask_object()
        elif command == "2":
            ui.clean_terminal()
            storage.input_txt()
        elif command == '3':
            ui.clean_terminal()
            print()
            show_all_movies()
        elif command == '4':
            ui.clean_terminal()
            error = model.mean_absolute_error(data,weights)
            print(f'\nСредняя ошибка модели: {round(error,2)}')
        elif command == '5':
            ui.clean_terminal()
            train_model(data, weights)   
        elif command == '6':
            ui.clean_terminal()
            print('Веса модели: \n')
            for weight, value in weights.items():
                print(f'{weight}: {round(value,2)}')
        elif command == "7":
            ui.clean_terminal()
            show_feature_importance(data)
        elif command == "8":
            model.one_to_one_error(data)
        elif command == "9":
            get_predict(weights)
        
        input('Enter, чтобы продолжить >>')


if __name__ == "__main__":
    main_loop()



