"""Console UI for local candidate search."""

from __future__ import annotations

from candidates.models import country_schema
from candidates.models import genre_schema
from candidates import service as candidate_service
from candidates.sources.tmdb import country_options as tmdb_country_options
from common import valid
from config import constant
from ui.console import request
from ui.console import ui


def show_global_candidate_search() -> None:
    """Shows saved candidate-pool search with filters, ranking and explanations."""
    ui.clean_terminal()
    overview = candidate_service.get_search_overview_view()
    if overview["is_empty"]:
        print("Общий пул кандидатов пуст.")
        return

    print("")
    for line in overview["lines"]:
        print(line)

    filters = request_search_candidate_filters()
    search_view = candidate_service.search_candidate_pool(overview["candidates"], filters)
    ranked_candidates = search_view["candidates"]
    if search_view["filtered_count"] == 0:
        print("\nПо выбранным фильтрам кандидатов не найдено.")
        return

    print(f"\nПосле выбранного фильтра: {search_view['filtered_count']}")

    top_n_value = request.loop_input(
        text="\nТоп N из общего пула >> ",
        funcs_list=[valid.is_correct_top_n],
    )
    top_n = min(int(top_n_value), len(ranked_candidates))

    ranking_view = candidate_service.rank_search_candidates(ranked_candidates)
    scored_candidates = ranking_view["candidates"]
    hidden_duplicates = ranking_view["hidden_duplicates"]
    if hidden_duplicates > 0:
        print(f"Дублей скрыто: {hidden_duplicates}")
    top_n = min(top_n, len(scored_candidates))

    print(f"\nТоп {top_n} из общего пула:\n")
    for index, row in enumerate(scored_candidates[:top_n], start=1):
        print_search_candidate_card(index, row)
    open_candidate_result_actions(scored_candidates[:top_n])


def _format_card_list(value) -> str:
    if isinstance(value, str):
        return value.strip() or "нет данных"
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value if str(item or "").strip()]
        return ", ".join(items) if items else "нет данных"
    if value in (None, ""):
        return "нет данных"
    return str(value)


def _format_card_score(value) -> str:
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return str(value)


def print_search_candidate_card(index: int, candidate: dict) -> None:
    title = candidate.get("title") or candidate.get("name") or candidate.get("title_ru") or "Без названия"
    year = candidate.get("year") or "?"
    countries = country_schema.candidate_country_for_display(candidate)
    genres = genre_schema.candidate_genres_for_display(candidate)
    description = candidate_service.format_candidate_description(candidate, limit=200)
    quality = candidate.get("quality_score")
    try:
        quality_label = f"{float(quality):.2f}"
    except (TypeError, ValueError):
        quality_label = "-"

    print(f"{index}. {title} ({year})")
    print(
        f"   TMDb: {_format_card_score(candidate.get('tmdb_score'))} "
        f"/ голосов: {candidate.get('tmdb_votes') or '-'}"
    )
    print(f"   Страна: {_format_card_list(countries)}")
    print(f"   Жанр: {_format_card_list(genres)}")
    print(f"   Описание: {description}")
    print(f"   Качество: {quality_label}")
    explanation = candidate.get("explanation") or []
    if explanation:
        print("   Почему в выдаче:")
        for reason in explanation[:6]:
            print(f"   - {reason}")
    print("")


def open_candidate_result_actions(candidates: list[dict]) -> None:
    if len(candidates) == 0:
        return
    selected = input("Номер кандидата для действия или Enter, чтобы вернуться >> ").strip()
    if selected == "":
        return
    if selected.isdigit() is False or not (1 <= int(selected) <= len(candidates)):
        print("Такого кандидата нет.")
        return

    candidate = candidates[int(selected) - 1]
    title = candidate.get("title") or "Без названия"
    print(f"\n{title}")
    print(" 1 >> Добавить в хочу посмотреть")
    print(" 2 >> Скрыть / не показывать")
    print(" 0 >> Назад")
    command = request.loop_input(
        text=">> ",
        funcs_list=[lambda value: value in {"0", "1", "2"}],
    )
    if command == "1":
        result = candidate_service.add_candidate_to_watchlist(candidate)
        print(f"Добавлено в хочу посмотреть. Всего в списке: {result['count']}")
    elif command == "2":
        result = candidate_service.hide_candidate(candidate)
        print(f"Кандидат скрыт. Всего скрытых: {result['count']}")


def _parse_optional_csv_list(value: str) -> list[str]:
    values = []
    for item in str(value or "").split(","):
        text = item.strip()
        if text != "":
            values.append(text)
    return values


def _format_search_default(value) -> str:
    if value in (None, ""):
        return "не важно"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if len(value) > 0 else "не важно"
    return str(value)


def _parse_optional_bounded_int(value: str, min_value: int, max_value: int) -> int | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        parsed = int(text)
    except ValueError:
        return None
    if parsed < min_value or parsed > max_value:
        return None
    return parsed


def _parse_optional_bounded_float(value: str, min_value: float, max_value: float) -> float | None:
    text = str(value or "").strip().replace(",", ".")
    if text == "":
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if parsed < min_value or parsed > max_value:
        return None
    return parsed


def _input_optional_search_int(label: str, default, min_value: int, max_value: int):
    answer = input(f"{label} [{_format_search_default(default)}] >> ").strip()
    if answer == "":
        return default
    return _parse_optional_bounded_int(answer, min_value, max_value)


def _input_optional_search_float(label: str, default, min_value: float, max_value: float):
    answer = input(f"{label} [{_format_search_default(default)}] >> ").strip()
    if answer == "":
        return default
    return _parse_optional_bounded_float(answer, min_value, max_value)


def parse_search_country_indexes(value: str, options_count: int) -> list[int] | None:
    text = str(value or "").strip()
    if text == "":
        return []
    indexes = []
    for part in text.replace(",", " ").split():
        try:
            index = int(part)
        except ValueError:
            return None
        if index < 1 or index > options_count:
            return None
        if index not in indexes:
            indexes.append(index)
    return indexes


def _print_country_options(output_func=print) -> None:
    for index, option in enumerate(tmdb_country_options.country_options(), start=1):
        output_func(f" {index} >> {option['label']}")


def choose_search_country() -> list[str]:
    options = tmdb_country_options.country_options()
    print("\nСтрана:")
    print("Введите номера стран из списка (можно несколько через запятую):")
    _print_country_options()

    while True:
        answer = input("\nВыбор [не важно] >> ").strip()
        if answer == "":
            return []
        indexes = parse_search_country_indexes(answer, len(options))
        if indexes is None:
            print("Введите номера стран через запятую, например: 1,4")
            continue
        return [options[index - 1]["code"] for index in indexes]


def parse_search_genre_indexes(value: str, options_count: int) -> list[int] | None:
    text = str(value or "").strip()
    if text == "":
        return []
    indexes = []
    for part in text.replace(",", " ").split():
        try:
            index = int(part)
        except ValueError:
            return None
        if index < 1 or index > options_count:
            return None
        if index not in indexes:
            indexes.append(index)
    return indexes


def _print_search_genre_options(genre_options: list[str], output_func=print) -> None:
    for index, label in enumerate(genre_options, start=1):
        output_func(f" {index} >> {label}")


def choose_search_genre_list(label: str, genre_options: list[str]) -> list[str]:
    if len(genre_options) == 0:
        return _input_optional_search_csv_list(label, [])

    print(f"\n{label}")
    _print_search_genre_options(genre_options)

    while True:
        answer = input("\nВыбор [не важно] >> ").strip()
        if answer == "":
            return []
        indexes = parse_search_genre_indexes(answer, len(genre_options))
        if indexes is None:
            print("Введите номера жанров через запятую, например: 1,3,5")
            continue
        return [genre_options[index - 1] for index in indexes]


def _input_optional_search_csv_list(label: str, default: list) -> list[str]:
    answer = input(f"{label} [{_format_search_default(default)}] >> ").strip()
    if answer == "":
        return list(default or [])
    return _parse_optional_csv_list(answer)


def request_search_candidate_filters() -> dict:
    print("\nФильтр кандидатов перед поиском:")
    print("Жанры для поиска (по сохранённым данным pool).")
    print("Жанры (saved pool / TMDb data).")
    print("Это не пересобирает pool и не делает новый TMDb-запрос.")
    print("Enter в списках стран/жанров = не важно; в числовых полях = saved default.\n")

    defaults_view = candidate_service.get_search_filter_defaults_view()
    defaults = defaults_view["defaults"]
    if defaults_view["has_defaults"]:
        print("\nDefaults общего pool:")
        for line in defaults_view["lines"]:
            print(f"  {line}")

    genre_options_view = candidate_service.get_search_genre_options_view()
    genre_options = genre_options_view["genres"]

    country = choose_search_country()
    year_min = _input_optional_search_int("Минимальный год", defaults.get("year_min"), 1900, constant.NOW_YEAR)
    year_max = _input_optional_search_int("Максимальный год", defaults.get("year_max"), 1900, constant.NOW_YEAR)
    include_genres = choose_search_genre_list("Включить жанры (saved pool)?", genre_options)
    exclude_genres = choose_search_genre_list("Исключить жанры (saved pool)?", genre_options)
    min_tmdb_score = _input_optional_search_float("Минимальный TMDb", defaults.get("min_tmdb_score"), 0.0, 10.0)
    min_tmdb_votes = _input_optional_search_int("Минимум голосов TMDb", defaults.get("min_tmdb_votes"), 0, 10_000_000)
    only_complete_default = defaults.get("only_complete", True)
    only_complete_label = "Y/n" if only_complete_default is True else "y/N"
    only_complete_answer = input(f"Только complete-кандидаты? [{only_complete_label}] >> ").strip().casefold()
    if only_complete_answer == "":
        only_complete = only_complete_default is True
    elif only_complete_answer in {"n", "no", "н", "нет"}:
        only_complete = False
    else:
        only_complete = only_complete_answer in {"y", "yes", "д", "да"}

    only_unwatched_answer = input("Скрывать просмотренные? [Y/n] >> ").strip().casefold()
    only_unwatched = only_unwatched_answer not in {"n", "no", "н", "нет"}
    hide_hidden_answer = input("Скрывать hidden? [Y/n] >> ").strip().casefold()
    hide_hidden = hide_hidden_answer not in {"n", "no", "н", "нет"}

    return {
        "criteria_name": None,
        "source": None,
        "country": country,
        "year_min": year_min,
        "year_max": year_max,
        "include_genres": include_genres,
        "exclude_genres": exclude_genres,
        "min_tmdb_score": min_tmdb_score,
        "min_tmdb_votes": min_tmdb_votes,
        "only_complete": only_complete,
        "only_unwatched": only_unwatched,
        "hide_hidden": hide_hidden,
    }
