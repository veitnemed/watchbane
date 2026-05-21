import constant

def predict_score(features: dict, weights = constant.DEFAULT_WEIGHTS) -> float:
    score = 0
    for k,v in weights.items():
        score += features[k]*v
    return score

def calc_error(movie: dict, weights = constant.DEFAULT_WEIGHTS) -> float:
    user_score = movie['user_score']
    score = predict_score(movie['features'],weights)
    return score - user_score

def mean_absolute_error(data: list, weights = constant.DEFAULT_WEIGHTS) -> float:
    l = len(data)
    absolute_error = 0
    if l == 0:
        return 0
    for obj in data:
       absolute_error += abs(calc_error(obj,weights))/l
    return absolute_error

def selection_weights(data: list, default_weights = constant.DEFAULT_WEIGHTS):
    
    if len(data) == 0:
        return default_weights.copy()
    weights_select = default_weights.copy()
    for feature in constant.FEATURES:     
        min_error = mean_absolute_error(data, weights_select)
        min_weight = weights_select[feature]
        for i in range(int(1/constant.STEP)+1):
            k = i*constant.STEP
            weights_select[feature] = k
            error = mean_absolute_error(data,weights_select)
            if min_error > error:
                min_error = error
                min_weight = k
        weights_select[feature] = min_weight
    return weights_select  

def one_to_one_error(data: list):
    
    lenth_data = len(data)
    meaen_error = 0
    for idx in range(lenth_data):
        new_data  = data.copy()
        new_data.pop(idx)
        user_score = data[idx]['user_score']
        new_w = selection_weights(new_data)  
        predict = predict_score(data[idx]["features"], new_w)
        error = abs(user_score-predict)
        
        print()
        print(f"{data[idx]['title']} ({round(user_score,1)})")
        print('Оценка модели:', round(predict,1))
        print('Ошибка: ',round(error,2))
        meaen_error += error/lenth_data
        
    print('Средняя ошибка: ', meaen_error)

def selection_weights_without_feature(
        data: list,
        excluded_feature,
        default_weights: dict = constant.DEFAULT_WEIGHTS
):
    if len(data) == 0:
        return default_weights.copy()

    weights_select = default_weights.copy()

    if excluded_feature in weights_select:
        weights_select.pop(excluded_feature)

    features = list(weights_select.keys())

    for feature in features:
        min_error = mean_absolute_error(data, weights_select)
        min_weight = weights_select[feature]

        for i in range(int(1 / constant.STEP) + 1):
            k = i * constant.STEP
            weights_select[feature] = k

            error = mean_absolute_error(data, weights_select)

            if error < min_error:
                min_error = error
                min_weight = k

        weights_select[feature] = min_weight

    return weights_select

