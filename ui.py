import os

def clean_terminal():
    os.system('cls')

def show_main_menu(movies_counter: int):
    print('===== TERMINAL MOVIES LERN =====')
    if movies_counter == 0:
        print('Датасет пуст!\n')
    else:
        print(f'Количество записей: {movies_counter}\n')
    print('1 >> Добавить запись')
    print('2 >> Импорт записей txt ')
    print('3 >> Показать все записи')
    print('4 >> Показать ошибку модели')
    print('5 >> Обучение')
    print('6 >> Показать веса ')
    print('7 >> Рассчёт влияния каждого параметра')
    print('8 >> Прогноз для каждого сериала')
    print("\n9 >> Сделать прогноз")
    print('0 >> Выход\n')


    


    