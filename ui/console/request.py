"""Запрашивает данные у пользователя и собирает объект фильма."""

import copy

from config import constant
from config import scheme
from common import valid
from storage import data as storage_data
from dataset import service
from dataset.models.media_type import MEDIA_TYPE_MOVIE, MEDIA_TYPE_TV, normalize_media_type
from dataset.resolve.defaults import merge_defaults
from dataset.resolve.genres import extract_tmdb_genres, split_known_genres
from ui.console import title_presenters
from candidates.sources.tmdb import country_options as tmdb_country_options


def get_request_schema() -> dict:
    """Собирает актуальную схему ручного ввода."""
    sections = [
        scheme.MAIN_INFO,
        scheme.RAW_SCORES,
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
            validators.append(storage_data.is_origin_title)
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
    """Возвращает доступные жанры TMDb в порядке candidate genre schema."""
    from candidates.models import genre_schema

    return list(genre_schema.GENRE_KEY_TO_DISPLAY.items())


def choose_genre_names_by_numbers(
    current_genres: list | None = None,
    *,
    prompt_title: str = "Выберите жанры по номерам через пробел.",
    prompt_hint: str = "Можно оставить пусто, тогда список жанров останется как есть.",
    input_label: str = "Номера жанров",
) -> list:
    """Дает выбрать известные жанры датасета по номерам."""
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


def confirm_or_edit_tmdb_genres(series: dict) -> list:
    """Показывает жанры из TMDb и дает принять или изменить их."""
    genres = extract_tmdb_genres(series)
    genres_line = ", ".join(genres) if len(genres) > 0 else "жанры не найдены"

    print(f"Краткое описание: {short_text(series.get('description'), 80)}")
    print(f"Жанры из TMDb: {genres_line}")
    answer = input("Принять жанры из TMDb? yes / edit >> ").strip().lower()
    if answer in ("yes", "y", "да"):
        return genres

    known_genres, unknown_genres = split_known_genres(genres)
    if len(unknown_genres) > 0:
        print(f"Как подсказка будут проигнорированы неизвестные жанры: {', '.join(unknown_genres)}")
    return choose_genre_names_by_numbers(
        known_genres,
        prompt_title="Выберите жанры для сохранения по номерам.",
        prompt_hint="Пустой ввод оставит текущий набор, 0 очистит жанры.",
        input_label="Номера жанров",
    )


def confirm_or_edit_dataset_genres(series: dict) -> list:
    """Показывает жанры для dataset без автодобавления новых feature."""
    genres = extract_tmdb_genres(series)
    known_genres, unknown_genres = split_known_genres(genres)
    genres_line = ", ".join(genres) if len(genres) > 0 else "жанры не найдены"
    known_line = ", ".join(known_genres) if len(known_genres) > 0 else "нет"

    print(f"Краткое описание: {short_text(series.get('description'), 80)}")
    print(f"Жанры из API: {genres_line}")
    print(f"В dataset попадут: {known_line}")
    if len(unknown_genres) > 0:
        print(f"Игнор как подсказка: {', '.join(unknown_genres)}")

    answer = input("Принять жанры для dataset? yes / edit / off >> ").strip().lower()
    if answer in ("yes", "y", "да"):
        return known_genres
    if answer in ("off", "n", "no", "нет"):
        return []

    return choose_genre_names_by_numbers(
        known_genres,
        prompt_title="Выберите жанры для dataset по номерам.",
        prompt_hint="Пустой ввод оставит текущий набор, 0 очистит жанры.",
        input_label="Номера жанров",
    )


def choose_media_type() -> str:
    answer = input("Media type [1=series, 2=movie] >> ").strip().lower()
    if answer in {"2", "movie", "film"}:
        return MEDIA_TYPE_MOVIE
    return MEDIA_TYPE_TV


def build_manual_defaults(input_title: str, base_defaults: dict | None = None, media_type: str = "tv") -> dict:
    """Собирает минимальные defaults для ручного добавления без SQL/API."""
    defaults = merge_defaults(
        service.build_empty_add_defaults(input_title, media_type=media_type),
        base_defaults or {},
    )
    defaults.setdefault(scheme.MAIN_INFO, {})["title"] = (
        defaults.get(scheme.MAIN_INFO, {}).get("title") or input_title
    )
    return defaults


def format_source(source: str | None) -> str:
    labels = {
        "tmdb_api": "TMDb API",
        "input": "ручной ввод",
        "manual": "ручной ввод",
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


def _format_tmdb_metric(value, source: str | None) -> str:
    if value is None or value == "":
        return "не заполнено"
    return f"{value} ({format_source(source)})"


def _poster_status(poster_hints: dict | None = None, meta_payload: dict | None = None) -> str | None:
    for payload in (poster_hints, meta_payload):
        if isinstance(payload, dict) is False:
            continue
        if payload.get("poster_url") not in (None, ""):
            return "найден poster_url"
        if payload.get("poster_path") not in (None, ""):
            return "найден poster_path"
    return None


def print_autofill_status(
    resolved: dict,
    *,
    manual_mode: bool,
    poster_hints: dict | None = None,
    meta_payload: dict | None = None,
) -> None:
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
    print(f"TMDb API: {statuses.get('tmdb_api', 'не найдено')}")
    print(f"TMDb score: {_format_tmdb_metric(raw_scores.get('tmdb_score'), sources.get('tmdb_score'))}")
    print(f"TMDb votes: {_format_tmdb_metric(raw_scores.get('tmdb_votes'), sources.get('tmdb_votes'))}")
    print(
        "TMDb popularity: "
        + _format_tmdb_metric(raw_scores.get("tmdb_popularity"), sources.get("tmdb_popularity"))
    )
    print(f"Жанры: {genres_text} ({format_source(genres_source)})" if genres else "Жанры: не заполнено")
    print(f"Описание: {format_value_with_source(short_text(description, 80), sources.get('description'))}")
    poster_status = _poster_status(poster_hints, meta_payload)
    if poster_status is not None:
        print(f"Постер: {poster_status}")
    print(f"Режим: {'ручная разметка' if manual_mode else 'автозаполнение + ручная проверка'}")


def ask_manual_addition() -> bool:
    answer = input("\nДанные не удалось получить автоматически.\nДобавить запись вручную? [y/N] ").strip().lower()
    return answer in {"y", "yes", "да", "д"}


def resolve_title_for_add(
    title: str,
    country: str = "Россия",
    confirm_genres: bool = False,
    media_type: str = "tv",
) -> tuple[dict | None, dict | None, dict | None]:
    """Ищет объект через TMDb и собирает defaults."""
    del confirm_genres

    def print_progress(_step: int, _total: int, message: str) -> None:
        print(message)

    normalized_media_type = normalize_media_type(media_type)
    resolved = service.resolve_title_data_for_add(
        title,
        country,
        on_progress=print_progress,
        media_type=normalized_media_type,
    )
    meta_payload = service.build_add_meta_payload(resolved)
    poster_hints = service.build_poster_hints_from_resolve(resolved)
    tmdb_data = resolved.get("tmdb_data")

    if resolved["found"] is False:
        error = resolved.get("tmdb_error") or {}
        details = error.get("details") or error.get("error") or "нет данных"
        print(f"\nTMDb не нашёл объект: {details}")
        if ask_manual_addition() is False:
            return None, None, None

        defaults = build_manual_defaults(resolved["title"], media_type=normalized_media_type)
        defaults[scheme.MAIN_INFO]["country"] = country
        print_autofill_status(resolved, manual_mode=True, poster_hints=poster_hints, meta_payload=meta_payload)
        return defaults, meta_payload, poster_hints

    defaults = resolved["defaults"]
    if isinstance(tmdb_data, dict):
        print("\nTMDb нашёл объект:")
        print(f"Название: {tmdb_data.get('title') or 'нет данных'}")
        print(f"Год: {tmdb_data.get('year') or 'нет данных'}")
        print(f"TMDb: {tmdb_data.get('tmdb_score') or '-'} / голосов {tmdb_data.get('tmdb_votes') or '-'}")
        print(f"Описание: {short_text(tmdb_data.get('overview'), 80) or 'нет данных'}")

    print_autofill_status(resolved, manual_mode=False, poster_hints=poster_hints, meta_payload=meta_payload)
    title_presenters.print_final_add_preview(defaults)
    answer = input("\nЭто нужный объект? Введи yes >> ").strip().lower()
    if answer != "yes":
        print("Операция отменена.")
        return None, None, None

    return defaults, meta_payload, poster_hints


def request_api_defaults(confirm_genres: bool = False) -> tuple[dict | None, dict | None, dict | None]:
    """Ищет сериал через API и возвращает значения для ручной формы."""
    title = loop_input(
        text="Название сериала >> ",
        funcs_list=[valid.is_correct_title]
    )
    media_type = choose_media_type()
    country = tmdb_country_options.choose_single_country_label()
    return resolve_title_for_add(title, country, confirm_genres, media_type=media_type)


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


def request_user_score(defaults: dict | None = None) -> dict:
    """Build add payload from resolved defaults; user may edit only user_score."""
    from dataset import service

    defaults = defaults or {}
    main_info = defaults.get(scheme.MAIN_INFO, {})
    default_score = main_info.get("user_score")

    print("\n--- Подтверждение ---")
    print("Название, год, TMDb-метаданные и жанры берутся из найденных данных без изменений.")
    title = main_info.get("title") or "?"
    year = main_info.get("year") or "?"
    print(f"Тайтл: {title} ({year})")

    field_settings = get_request_schema()[scheme.MAIN_INFO]["user_score"]
    field_validators = get_validators(field_settings["tag"])
    answer = loop_input_with_default(
        text=f'>> {get_label("user_score")} [{default_score}]: ',
        funcs_list=field_validators,
        default_value=default_score,
    )
    user_score = valid.parse_float(answer)
    return service.build_movie_record_from_defaults(defaults, user_score)


def request_all_scores(defaults: dict = None) -> dict:
    """Запрашивает все данные фильма."""
    if defaults is None:
        defaults = {}
    funcs = get_request_schema()

    movie = {}

    for section_name, section_fields in funcs.items():
        section = {}

        print(f'\n--- {get_section_label(section_name)} ---')

        for feature, field_settings in section_fields.items():
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
