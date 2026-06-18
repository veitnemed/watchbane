"""Запрашивает данные у пользователя и собирает объект фильма."""

import copy

from config import constant
from config import scheme
from common import format_score
from common import valid
from data_work import storage
from data_work import title_resolve
from ui import title_presenters


def get_request_schema() -> dict:
    """Собирает актуальную схему ручного ввода."""
    sections = [
        scheme.MAIN_INFO,
        scheme.RAW_SCORES,
        scheme.TAGS_VIBE,
        scheme.GENRE,
    ]
    return {
        section_name: copy.deepcopy(scheme.get_schema(section_name))
        for section_name in sections
    }


def get_validators(tags_validators: list, max_value: int = 1) -> list:
    """Собирает валидаторы для поля схемы."""
    validators = []
    for tag in tags_validators:
        if tag == "tags_score":
            validators.append(lambda value, max_value=max_value: valid.is_tags_score(value, max_value))
        elif tag == "origin_title":
            validators.append(storage.is_origin_title)
        else:
            validators.append(valid.VALIDATORS[tag])
    return validators


def get_label(feature: str) -> str:
    """Возвращает подпись поля."""
    return constant.FIELD_LABELS.get(feature, feature)


def get_section_label(section_name: str) -> str:
    """Возвращает подпись секции."""
    return constant.SECTION_LABELS.get(section_name, section_name)


def loop_input(text, funcs_list):
    """Запрашивает ввод до прохождения проверок."""
    while True:
        value = input(text)
        for func in funcs_list:
            if func(value) is False:
                break
        else:
            break
    return value


def loop_input_with_default(text: str, funcs_list: list, default_value=None):
    """Запрашивает ввод и подставляет значение по умолчанию при пустом ответе."""
    while True:
        value = input(text)
        if value.strip() == "" and default_value is not None:
            value = str(default_value)
        for func in funcs_list:
            if func(value) is False:
                break
        else:
            break
    return value


def short_text(value, limit: int = 50) -> str:
    """Обрезает текст для короткого предпросмотра."""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _available_genre_options() -> list[tuple[str, str]]:
    """Возвращает доступные жанры модели в порядке текущей схемы."""
    options = []
    for feature in constant.GENRE:
        label = get_label(feature)
        options.append((feature, label))
    return options


def choose_genre_names_by_numbers(
    current_genres: list | None = None,
    *,
    prompt_title: str = "Выберите жанры по номерам через пробел.",
    prompt_hint: str = "Можно оставить пусто, тогда список жанров останется как есть.",
    input_label: str = "Номера жанров",
) -> list:
    """Дает выбрать известные жанры модели по номерам."""
    if current_genres is None:
        current_genres = []

    options = _available_genre_options()
    if len(options) == 0:
        print("Список жанров пока пуст.")
        return current_genres

    print(prompt_title)
    print(f"{prompt_hint}\n")
    for idx, (_, label) in enumerate(options, start=1):
        print(f"{idx}. {label}")

    current_label = ", ".join(current_genres) if len(current_genres) > 0 else "пусто"
    while True:
        answer = input(f"\n{input_label} [{current_label}] >> ").strip()
        if answer == "":
            return current_genres
        if answer == "0":
            return []

        parts = answer.split()
        selected_indexes = []
        for part in parts:
            try:
                index = int(part)
            except ValueError:
                selected_indexes = []
                break
            if 1 <= index <= len(options):
                selected_indexes.append(index)
            else:
                selected_indexes = []
                break

        if len(selected_indexes) == 0:
            print("Введите номера жанров через пробел, например: 1 2 3. Для очистки можно ввести 0.")
            continue

        selected_genres = []
        for index in selected_indexes:
            genre_name = options[index - 1][1]
            if genre_name not in selected_genres:
                selected_genres.append(genre_name)
        return selected_genres


def choose_genre_values_by_numbers(default_values: dict | None = None) -> dict:
    """Собирает секцию genre через выбор жанров по номерам."""
    if default_values is None:
        default_values = {}

    options = _available_genre_options()
    selected_features = [
        feature for feature, _ in options
        if int(default_values.get(feature, 0) or 0) == 1
    ]
    selected_labels = [get_label(feature) for feature in selected_features]

    selected_genres = choose_genre_names_by_numbers(
        selected_labels,
        prompt_title="Доступные жанры модели:",
        prompt_hint="Выберите жанры по номерам через пробел. Пустой ввод оставит значения по умолчанию, 0 очистит выбор.",
        input_label="Номера жанров",
    )

    selected_set = set(selected_genres)
    genre_values = {}
    for feature, label in options:
        genre_values[feature] = 1 if label in selected_set else 0
    return genre_values


def confirm_or_edit_api_genres(series: dict) -> list:
    """Показывает жанры из API и дает принять или изменить их."""
    genres = title_resolve.extract_api_genres(series)
    genres_line = ", ".join(genres) if len(genres) > 0 else "жанры не найдены"

    print(f"Краткое описание: {short_text(series.get('description'), 80)}")
    print(f"Жанры из API: {genres_line}")
    answer = input("Принять жанры из API? yes / edit >> ").strip().lower()
    if answer in ("yes", "y", "да"):
        return genres

    known_genres, unknown_genres = title_resolve.split_known_genres(genres)
    if len(unknown_genres) > 0:
        print(f"Как подсказка будут проигнорированы неизвестные жанры: {', '.join(unknown_genres)}")
    return choose_genre_names_by_numbers(
        known_genres,
        prompt_title="Выберите жанры для сохранения по номерам.",
        prompt_hint="Пустой ввод оставит текущий набор, 0 очистит жанры.",
        input_label="Номера жанров",
    )


def confirm_or_edit_model_genres(series: dict) -> list:
    """Показывает жанры для модели без автодобавления новых feature."""
    genres = title_resolve.extract_api_genres(series)
    known_genres, unknown_genres = title_resolve.split_known_genres(genres)
    genres_line = ", ".join(genres) if len(genres) > 0 else "жанры не найдены"
    known_line = ", ".join(known_genres) if len(known_genres) > 0 else "нет"

    print(f"Краткое описание: {short_text(series.get('description'), 80)}")
    print(f"Жанры из API: {genres_line}")
    print(f"В модель попадут: {known_line}")
    if len(unknown_genres) > 0:
        print(f"Игнор как подсказка: {', '.join(unknown_genres)}")

    answer = input("Принять жанры для модели? yes / edit / off >> ").strip().lower()
    if answer in ("yes", "y", "да"):
        return known_genres
    if answer in ("off", "n", "no", "нет"):
        return []

    return choose_genre_names_by_numbers(
        known_genres,
        prompt_title="Выберите жанры для модели по номерам.",
        prompt_hint="Пустой ввод оставит текущий набор, 0 очистит жанры.",
        input_label="Номера жанров",
    )


def build_manual_defaults(input_title: str, base_defaults: dict | None = None) -> dict:
    """Собирает минимальные defaults для ручного добавления без SQL/API."""
    defaults = title_resolve.merge_defaults(
        title_resolve.build_empty_add_defaults(input_title),
        base_defaults or {},
    )
    defaults.setdefault(scheme.MAIN_INFO, {})["title"] = (
        defaults.get(scheme.MAIN_INFO, {}).get("title") or input_title
    )
    return defaults


def format_source(source: str | None) -> str:
    labels = {
        "imdb_sql": "IMDb SQL",
        "kp_api": "KP API",
        "tmdb_api": "TMDb API",
        "input": "ручной ввод",
    }
    return labels.get(source or "", "не заполнено")


def format_value_with_source(value, source: str | None) -> str:
    if value is None or value == "":
        return "не заполнено"
    return f"{value} ({format_source(source)})"


def format_score_pair(score, votes, score_source: str | None, votes_source: str | None) -> str:
    if score is None and votes is None:
        return "не заполнено"
    score_text = "-" if score is None else str(score)
    votes_text = "-" if votes is None else str(votes)
    if score_source == votes_source:
        return f"{score_text} / голосов {votes_text} ({format_source(score_source)})"
    return (
        f"{score_text} ({format_source(score_source)}) / "
        f"голосов {votes_text} ({format_source(votes_source)})"
    )


def print_autofill_status(resolved: dict, *, manual_mode: bool) -> None:
    """Показывает, откуда взялись defaults для формы добавления."""
    statuses = resolved.get("statuses", {})
    defaults = resolved.get("defaults") or build_manual_defaults(resolved.get("title", ""))
    raw_scores = defaults.get(scheme.RAW_SCORES, {})
    sources = resolved.get("sources", {})
    source_values = resolved.get("source_values", {})
    genres = source_values.get("genres") or []
    genres_text = ", ".join(genres) if len(genres) > 0 else "не заполнено"
    genres_source = sources.get("genres")
    description = source_values.get("description")

    print("\nАвтозаполнение:")
    print(f"SQL: {statuses.get('sql', 'не найдено')}")
    print(f"KP API: {statuses.get('kp_api', 'не найдено')}")
    print(f"TMDb API: {statuses.get('tmdb_api', 'не найдено')}")
    print("")
    print(
        "IMDb: "
        + format_score_pair(
            raw_scores.get("imdb_score"),
            raw_scores.get("imdb_votes"),
            sources.get("imdb_score"),
            sources.get("imdb_votes"),
        )
    )
    print(
        "KP: "
        + format_score_pair(
            raw_scores.get("kp_score"),
            raw_scores.get("kp_votes"),
            sources.get("kp_score"),
            sources.get("kp_votes"),
        )
    )
    print(f"Жанры: {genres_text} ({format_source(genres_source)})" if genres else "Жанры: не заполнено")
    print(f"Описание: {format_value_with_source(short_text(description, 80), sources.get('description'))}")
    print(f"Режим: {'ручная разметка' if manual_mode else 'автозаполнение + ручная проверка'}")


def ask_manual_addition() -> bool:
    answer = input("\nДанные не удалось получить автоматически.\nДобавить запись вручную? [y/N] ").strip().lower()
    return answer in {"y", "yes", "да", "д"}


def resolve_title_for_training(title: str, country: str = "Россия", confirm_genres: bool = False) -> dict | None:
    """Ищет объект через SQL, затем обогащает через API и собирает defaults."""
    resolved = title_resolve.resolve_title_data_for_add(title, country)
    sql_data = resolved["sql_data"]
    api_data = resolved["api_data"]

    if sql_data is not None:
        title_presenters.print_sql_training_preview(sql_data)
    else:
        print(f"\nSQL не нашёл точный базовый объект: {resolved['sql_result'].get('details')}")

    api_defaults = {}
    if api_data is not None:
        title_presenters.print_api_training_preview(api_data)
        api_genres = title_resolve.extract_api_genres(api_data)
        if confirm_genres:
            print("")
            api_genres = confirm_or_edit_model_genres(api_data)
        api_defaults = title_resolve.build_api_defaults(api_data, api_genres)
    elif resolved["api_error"] is not None:
        error = resolved["api_error"]
        print(f"\nAPI не обогатил объект: {error.get('details') or error.get('error')}")

    if resolved["found"] is False:
        print("\nНе удалось найти объект ни в SQL, ни в API.")
        if ask_manual_addition() is False:
            return None

        defaults = build_manual_defaults(resolved["title"])
        print_autofill_status(resolved, manual_mode=True)
        return defaults

    defaults = resolved["defaults"]
    if confirm_genres and api_data is not None:
        defaults[scheme.GENRE] = dict(api_defaults.get(scheme.GENRE, {}))

    print_autofill_status(resolved, manual_mode=api_data is None)
    title_presenters.print_final_training_preview(defaults)
    answer = input("\nЭто нужный объект? Введи yes >> ").strip().lower()
    if answer != "yes":
        print("Операция отменена.")
        return None

    return defaults


def request_api_defaults(confirm_genres: bool = False) -> dict:
    """Ищет сериал через API и возвращает значения для ручной формы."""
    title = loop_input(
        text="Название сериала >> ",
        funcs_list=[valid.is_correct_title]
    )
    country = "Россия"
    return resolve_title_for_training(title, country, confirm_genres)


def request_predict_features(defaults: dict) -> dict:
    """Запрашивает данные для прогноза и собирает признаки модели."""
    funcs = get_request_schema()
    main_info = {}
    raw_scores = {}
    tags_vibe = {}
    genre_values = {}

    print(f'\n--- {get_section_label(scheme.MAIN_INFO)} ---')
    year_settings = funcs[scheme.MAIN_INFO]["year"]
    year_default = defaults.get(scheme.MAIN_INFO, {}).get("year")
    year_answer = loop_input_with_default(
        text=f'>> {get_label("year")} [{year_default}]: ',
        funcs_list=get_validators(year_settings["tag"]),
        default_value=year_default
    )
    main_info["year"] = int(year_answer)

    print(f'\n--- {get_section_label(scheme.RAW_SCORES)} ---')
    for feature, field_settings in funcs[scheme.RAW_SCORES].items():
        default_value = defaults.get(scheme.RAW_SCORES, {}).get(feature)
        answer = loop_input_with_default(
            text=f'>> {get_label(feature)} [{default_value}]: ',
            funcs_list=get_validators(field_settings["tag"]),
            default_value=default_value
        )
        if field_settings["type"] is float:
            raw_scores[feature] = valid.parse_float(answer)
        else:
            raw_scores[feature] = field_settings["type"](answer)

    print(f'\n--- {get_section_label(scheme.TAGS_VIBE)} ---')
    for feature, field_settings in funcs[scheme.TAGS_VIBE].items():
        show_score_help(feature)
        default_value = defaults.get(scheme.TAGS_VIBE, {}).get(feature, 0)
        answer = loop_input_with_default(
            text=f'>> {get_label(feature)} [{default_value}]: ',
            funcs_list=get_validators(field_settings["tag"], field_settings.get("max_value", 1)),
            default_value=default_value
        )
        tags_vibe[feature] = int(answer)

    print(f'\n--- {get_section_label(scheme.GENRE)} ---')
    genre_values = choose_genre_values_by_numbers(defaults.get(scheme.GENRE, {}))

    features = {
        constant.BIAS_FEATURE: 1.0
    }
    features.update(format_score.raw_to_struct(raw_scores, main_info))
    features.update(format_score.tags_to_features(tags_vibe))
    features.update(format_score.tags_to_features(genre_values, scheme.GENRE))
    return features


def show_score_help(feature: str) -> None:
    """Показывает подсказку по шкале тега."""
    help_info = constant.TAG_RULES.get(feature)
    if help_info is None:
        return

    print("\n" + "-" * 40)
    print(help_info["title"])
    print(help_info["question"])
    print("Шкала оценки:")
    for line in help_info["scale"]:
        print(f"  {line}")


def request_all_scores(defaults: dict = None) -> dict:
    """Запрашивает все данные фильма."""
    if defaults is None:
        defaults = {}
    funcs = get_request_schema()

    movie = {}

    for section_name, section_fields in funcs.items():
        section = {}

        print(f'\n--- {get_section_label(section_name)} ---')

        if section_name == scheme.GENRE:
            movie[section_name] = choose_genre_values_by_numbers(defaults.get(section_name, {}))
            continue

        for feature, field_settings in section_fields.items():
            if section_name == scheme.TAGS_VIBE:
                show_score_help(feature)

            tags_validators = field_settings["tag"]
            type_func = field_settings["type"]
            field_validators = get_validators(tags_validators, field_settings.get("max_value", 1))
            default_value = defaults.get(section_name, {}).get(feature)
            answer = loop_input_with_default(
                text=f'>> {get_label(feature)} [{default_value}]: ',
                funcs_list=field_validators,
                default_value=default_value
            )
            if type_func is float:
                section[feature] = valid.parse_float(answer)
            else:
                section[feature] = type_func(answer)

        movie[section_name] = section

    return movie
