d = {
        "main_info": {
            "title": "Чужие деньги",
            "user_score": 8.3,
            "year": 2025
        },
        "raw_scores": {
            "kp_score": 8.0,
            "kp_votes": 128536,
            "imdb_score": 6.3,
            "imdb_votes": 141
        },
        "computed_scores": {
            "kp_score": 8.0,
            "kp_popularity": 4.75473988715031,
            "imdb_score": 6.3,
            "imdb_popularity": 2.9040420888852436
        },
        "tags_vibe": {
            "ivestigation": 1,
            "is_ivi": 1,
            "is_kinopoisk": 0,
            "is_okko": 0,
            "is_tnt": 0,
            "is_tv_3": 0,
            "is_premier": 0,
            "is_kion": 0,
            "is_wink": 0,
            "is_more_tv": 0,
            "is_start": 0
        }
}

del d["main_info"]


print(d)
def get_one_dict(obj: dict):
    res = {}
    dict_list = list(obj.values())
    for d in dict_list:
        res.update(d)
    return res

