"""Поиск тайтла через SQL и API и сбор defaults без UI."""

from config import constant
from config import genre_tags
from config import scheme
from apis import imdb_sql as sql_search
from apis import kp_api as api

try:
    from apis import tmdb_api as api_tmdb
except ImportError:  # pragma: no cover - TMDb fallback is optional for old environments.
    api_tmdb = None


def unique_preserve_order(values: list) -> list:
    """Убирает дубли, сохраняя исходный порядок элементов."""
    result = []
    for value in values:
        text = str(value or "").strip()
        if text == "" or text in result:
            continue
        result.append(text)
    return result


def print_progress_step(source: str, status: str) -> None:
    print(f"{source}: {status}")


def split_known_genres(genres: list) -> tuple[list, list]:
    """Разделяет жанры на известные модели и неизвестные подсказки."""
    known_features = set(genre_tags.get_genre_fields())
    known = []
    unknown = []

    for genre_name in unique_preserve_order(genres):
        feature = genre_tags.genre_to_feature_name(genre_name)
        if feature in known_features:
            known.append(genre_name)
        else:
            unknown.append(genre_name)

    return known, unknown


def extract_api_genres(series: dict) -> list:
    """Извлекает список жанров из ответа API или плоского кандидата."""
    genres = []
    for item in series.get("genres", []) or []:
        if isinstance(item, dict) and item.get("name"):
            genres.append(str(item["name"]).strip())
        elif isinstance(item, str):
            genres.append(item.strip())
    return genres


def extract_api_title(series: dict) -> str:
    """Достаёт лучшее доступное название из сырого ответа API."""
    for key in ("title", "name", "alternativeName", "enName"):
        value = series.get(key)
        if str(value or "").strip() != "":
            return str(value).strip()
    return ""


def extract_api_raw_scores(series: dict) -> dict:
    """Собирает рейтинги и голоса из ответа API в плоский словарь."""
    return {
        "kp_score": series.get("kp_score", api.safe_nested(series, "rating", "kp")),
        "kp_votes": series.get("kp_votes", api.safe_nested(series, "votes", "kp")),
        "imdb_score": series.get("imdb_score", api.safe_nested(series, "rating", "imdb")),
        "imdb_votes": series.get("imdb_votes", api.safe_nested(series, "votes", "imdb")),
    }


def extract_api_description(series: dict) -> str:
    """Возвращает лучшее доступное описание из KP API."""
    return str(series.get("description") or series.get("shortDescription") or "").strip()


def build_genre_defaults(genres: list) -> dict:
    """Собирает значения genre по списку жанров."""
    genre_defaults = {feature: 0 for feature in constant.GENRE}
    known_genres, _ = split_known_genres(genres)
    for genre_name in known_genres:
        feature = genre_tags.genre_to_feature_name(genre_name)
        if feature in genre_defaults:
            genre_defaults[feature] = 1
    return genre_defaults


def build_empty_add_defaults(input_title: str) -> dict:
    """Собирает минимальные defaults для ручного добавления без внешних данных."""
    return {
        scheme.MAIN_INFO: {
            "title": input_title,
            "user_score": None,
            "year": None,
        },
        scheme.RAW_SCORES: {
            "kp_score": None,
            "kp_votes": None,
            "imdb_score": None,
            "imdb_votes": None,
        },
        scheme.TAGS_VIBE: {feature: 0 for feature in constant.TAGS_VIBE},
        scheme.GENRE: {feature: 0 for feature in constant.GENRE},
    }


def build_sql_defaults(series: dict) -> dict:
    """Собирает значения по умолчанию из локального SQL-результата."""
    genres = unique_preserve_order(series.get("genres", []) or [])
    genre_defaults = build_genre_defaults(genres)

    return {
        scheme.MAIN_INFO: {
            "title": series.get("title") or series.get("original_title"),
            "user_score": None,
            "year": series.get("year"),
        },
        scheme.RAW_SCORES: {
            "kp_score": None,
            "kp_votes": None,
            "imdb_score": series.get("imdb_rating"),
            "imdb_votes": series.get("imdb_votes"),
        },
        scheme.TAGS_VIBE: {},
        scheme.GENRE: genre_defaults,
    }


def merge_defaults(base: dict, extra: dict) -> dict:
    """Объединяет defaults из нескольких источников с приоритетом extra."""
    merged = {
        scheme.MAIN_INFO: {},
        scheme.RAW_SCORES: {},
        scheme.TAGS_VIBE: {},
        scheme.GENRE: {},
    }

    for section_name in merged.keys():
        base_section = base.get(section_name, {}) if isinstance(base, dict) else {}
        extra_section = extra.get(section_name, {}) if isinstance(extra, dict) else {}

        if section_name == scheme.GENRE:
            keys = set(base_section.keys()) | set(extra_section.keys())
            for key in keys:
                merged[section_name][key] = max(
                    int(base_section.get(key, 0) or 0),
                    int(extra_section.get(key, 0) or 0),
                )
            continue

        merged[section_name].update(base_section)
        for key, value in extra_section.items():
            if value is not None and value != "":
                merged[section_name][key] = value
            elif key not in merged[section_name]:
                merged[section_name][key] = value

    return merged


def build_api_defaults(series: dict, genres: list | None = None) -> dict:
    """Собирает значения API для подстановки в ручную форму."""
    if genres is None:
        genres = extract_api_genres(series)

    genre_defaults = build_genre_defaults(genres)
    raw_scores = extract_api_raw_scores(series)

    return {
        scheme.MAIN_INFO: {
            "title": extract_api_title(series),
            "user_score": None,
            "year": series.get("year"),
        },
        scheme.RAW_SCORES: {
            "kp_score": raw_scores.get("kp_score"),
            "kp_votes": raw_scores.get("kp_votes"),
            "imdb_score": raw_scores.get("imdb_score"),
            "imdb_votes": raw_scores.get("imdb_votes"),
        },
        scheme.TAGS_VIBE: {},
        scheme.GENRE: genre_defaults,
    }


def build_candidate_meta_payload(candidate: dict) -> dict:
    """Собирает дополнительный meta-payload для переноса кандидата в dataset."""
    payload = {}
    for key in ("tmdb_id", "imdb_id", "kp_id", "description", "source"):
        if key not in candidate:
            continue
        value = candidate.get(key)
        if value is None or value == "":
            continue
        payload[key] = value
    return payload


def build_candidate_transfer_payload(candidate: dict) -> dict:
    """Собирает defaults и meta для переноса кандидата из общего пула в dataset."""
    defaults = build_api_defaults(candidate)
    meta_payload = build_candidate_meta_payload(candidate)
    return {
        "defaults": defaults,
        "meta_payload": meta_payload,
    }


def extract_tmdb_genres(series: dict | None) -> list:
    """Достаёт список жанров из нормализованного TMDb-объекта."""
    if not isinstance(series, dict):
        return []
    return unique_preserve_order(series.get("genres_tmdb", []) or [])


def extract_tmdb_title(series: dict | None) -> str:
    """Возвращает название из нормализованного TMDb-объекта."""
    if not isinstance(series, dict):
        return ""
    for key in ("title", "original_title"):
        value = str(series.get(key) or "").strip()
        if value:
            return value
    return ""


def search_tmdb_defaults_data(queries: list) -> dict:
    """Ищет TMDb-кандидата для add-flow и возвращает нормализованные данные без падения UI."""
    if api_tmdb is None:
        return {
            "data": None,
            "error": {"ok": False, "error": "tmdb_unavailable", "details": "TMDb module is unavailable"},
            "status": "ошибка",
        }

    last_error = None
    for query in unique_preserve_order(queries):
        try:
            results = api_tmdb.search_tv_by_name(query)
            selected = api_tmdb.choose_best_result(results)
            if selected is None:
                last_error = {"ok": False, "error": "not_found", "details": f"TMDb не нашёл: {query}"}
                continue
            details = api_tmdb.get_tv_details(int(selected["id"]))
            return {
                "data": api_tmdb.normalize_tmdb_tv(details),
                "error": None,
                "status": "найдено",
            }
        except Exception as error:  # noqa: BLE001 - внешний API не должен ронять ручное добавление.
            last_error = {"ok": False, "error": "network_error", "details": str(error)}

    if last_error is None:
        last_error = {"ok": False, "error": "not_found", "details": "TMDb не нашёл объект"}
    status = "не найдено" if last_error.get("error") == "not_found" else "ошибка"
    return {
        "data": None,
        "error": last_error,
        "status": status,
    }


def first_value(*items):
    """Возвращает первое непустое значение и его источник."""
    for value, source in items:
        if value is not None and value != "" and value != []:
            return value, source
    return None, None


def build_add_defaults_by_priority(input_title: str, sql_data: dict | None, api_data: dict | None, tmdb_data: dict | None) -> dict:
    """Собирает defaults для добавления записи по зафиксированным приоритетам источников."""
    defaults = build_empty_add_defaults(input_title)
    sources = {
        "title": None,
        "year": None,
        "imdb_score": None,
        "imdb_votes": None,
        "kp_score": None,
        "kp_votes": None,
        "genres": None,
        "description": None,
    }
    source_values = {
        "genres": [],
        "description": None,
    }

    api_scores = extract_api_raw_scores(api_data) if api_data is not None else {}
    api_genres = extract_api_genres(api_data) if api_data is not None else []
    sql_genres = unique_preserve_order((sql_data or {}).get("genres", []) or [])
    tmdb_genres = extract_tmdb_genres(tmdb_data)

    title_value, title_source = first_value(
        (extract_api_title(api_data) if api_data is not None else None, "kp_api"),
        (input_title, "input"),
        (extract_tmdb_title(tmdb_data), "tmdb_api"),
        ((sql_data or {}).get("title") or (sql_data or {}).get("original_title"), "imdb_sql"),
    )
    year_value, year_source = first_value(
        ((api_data or {}).get("year"), "kp_api"),
        ((sql_data or {}).get("year"), "imdb_sql"),
        ((tmdb_data or {}).get("year"), "tmdb_api"),
    )
    imdb_score, imdb_score_source = first_value(
        ((sql_data or {}).get("imdb_rating"), "imdb_sql"),
        (api_scores.get("imdb_score"), "kp_api"),
    )
    imdb_votes, imdb_votes_source = first_value(
        ((sql_data or {}).get("imdb_votes"), "imdb_sql"),
        (api_scores.get("imdb_votes"), "kp_api"),
    )
    kp_score, kp_score_source = first_value((api_scores.get("kp_score"), "kp_api"))
    kp_votes, kp_votes_source = first_value((api_scores.get("kp_votes"), "kp_api"))
    genres, genres_source = first_value(
        (api_genres, "kp_api"),
        (tmdb_genres, "tmdb_api"),
        (sql_genres, "imdb_sql"),
    )
    description, description_source = first_value(
        (extract_api_description(api_data) if api_data is not None else None, "kp_api"),
        ((tmdb_data or {}).get("overview"), "tmdb_api"),
    )

    defaults[scheme.MAIN_INFO]["title"] = title_value or input_title
    defaults[scheme.MAIN_INFO]["year"] = year_value
    defaults[scheme.RAW_SCORES]["imdb_score"] = imdb_score
    defaults[scheme.RAW_SCORES]["imdb_votes"] = imdb_votes
    defaults[scheme.RAW_SCORES]["kp_score"] = kp_score
    defaults[scheme.RAW_SCORES]["kp_votes"] = kp_votes
    defaults[scheme.GENRE] = build_genre_defaults(genres or [])

    sources["title"] = title_source
    sources["year"] = year_source
    sources["imdb_score"] = imdb_score_source
    sources["imdb_votes"] = imdb_votes_source
    sources["kp_score"] = kp_score_source
    sources["kp_votes"] = kp_votes_source
    sources["genres"] = genres_source
    sources["description"] = description_source
    source_values["genres"] = genres or []
    source_values["description"] = description

    return {
        "defaults": defaults,
        "sources": sources,
        "source_values": source_values,
    }


def get_kp_status(api_data: dict | None, api_error: dict | None) -> str:
    """Возвращает короткий статус KP API для отчёта автозаполнения."""
    if api_data is not None:
        return "найдено"
    if api_error is None:
        return "не найдено"
    if api_error.get("error") in {"not_found", "country_not_found"}:
        return "не найдено"
    return "ошибка"


def resolve_title_data_for_add(title: str, country: str = "Россия") -> dict:
    """Собирает defaults для добавления записи по приоритетам SQL -> KP -> TMDb -> ручной ввод."""
    title = api.normalize_text(title)
    country = api.normalize_text(country)

    print_progress_step("IMDb dataset", "Поиск")
    sql_result = sql_search.search_title_in_sql(title, country)
    sql_data = sql_result["data"] if sql_result["ok"] else None
    print_progress_step("IMDb dataset", "Успешно" if sql_data is not None else "Нет кандидатов")

    api_data = None
    last_api_error = None
    api_queries = unique_preserve_order([
        title,
        (sql_data or {}).get("title"),
        (sql_data or {}).get("original_title"),
    ])
    print_progress_step("KP API", "Ожидание ответа")
    for query in api_queries:
        api_result = api.find_series_raw(query, country)
        if api_result["ok"]:
            api_data = api_result["data"]
            break
        last_api_error = api_result
    kp_status = get_kp_status(api_data, last_api_error)
    if kp_status == "найдено":
        print_progress_step("KP API", "Успешно")
    elif kp_status == "ошибка":
        print_progress_step("KP API", "Ошибка сети")
    else:
        print_progress_step("KP API", "Нет кандидатов")

    tmdb_data = None
    tmdb_error = None
    tmdb_status = "не найдено"
    if api_data is None:
        print_progress_step("TMDb API", "Ожидание ответа")
        tmdb_result = search_tmdb_defaults_data(api_queries)
        tmdb_data = tmdb_result["data"]
        tmdb_error = tmdb_result["error"]
        tmdb_status = tmdb_result["status"]
        if tmdb_status == "найдено":
            print_progress_step("TMDb API", "Успешно")
        elif tmdb_status == "ошибка":
            print_progress_step("TMDb API", "Ошибка сети")
        else:
            print_progress_step("TMDb API", "Нет кандидатов")
    else:
        print_progress_step("TMDb API", "Не требуется")

    found = sql_data is not None or api_data is not None or tmdb_data is not None
    defaults = None
    sources = {}
    source_values = {}
    if found:
        built = build_add_defaults_by_priority(title, sql_data, api_data, tmdb_data)
        defaults = built["defaults"]
        sources = built["sources"]
        source_values = built["source_values"]

    return {
        "title": title,
        "country": country,
        "sql_result": sql_result,
        "sql_data": sql_data,
        "api_data": api_data,
        "api_error": last_api_error,
        "tmdb_data": tmdb_data,
        "tmdb_error": tmdb_error,
        "defaults": defaults,
        "sources": sources,
        "source_values": source_values,
        "statuses": {
            "sql": "найдено" if sql_data is not None else "не найдено",
            "kp_api": get_kp_status(api_data, last_api_error),
            "tmdb_api": tmdb_status,
        },
        "found": found,
    }


def resolve_title_data(title: str, country: str = "Россия") -> dict:
    """Совместимое имя: add-flow использует единые приоритеты источников."""
    return resolve_title_data_for_add(title, country)
