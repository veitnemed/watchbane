
my_dict = {
    '1': 2,
    '2': 3,
    '3': {
        'a': 'a',
        'b': 'b',
        'c': 'c'
    }
}

my_dict['3']['d'] = 'd'
print(my_dict['3'])