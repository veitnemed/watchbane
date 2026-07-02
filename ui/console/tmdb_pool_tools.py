"""Console workflows for TMDb candidate pool build and import flows."""

from config import constant
from candidates import service as candidate_service
from candidates.sources.tmdb import country_options as tmdb_country_options
from candidates.sources.tmdb import genre_options as tmdb_genre_options
from storage import data as storage_data
from ui.console import request
from ui.console import ui


def _parse_bounded_int(value: str, default: int, min_value: int, max_value: int) -> int:
    try:
        number = int(str(value or "").strip())
    except ValueError:
        number = default
    return max(min_value, min(number, max_value))


def _parse_optional_bounded_int(value: str, min_value: int, max_value: int) -> int | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        number = int(text)
    except ValueError:
        return None
    return max(min_value, min(number, max_value))


def _parse_optional_bounded_float(value: str, min_value: float, max_value: float) -> float | None:
    text = str(value or "").strip().replace(",", ".")
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return max(min_value, min(number, max_value))


def _parse_iso_country_code(value: str) -> str | None:
    country = str(value or "").strip().upper()
    if len(country) == 2 and country.isascii() and country.isalpha():
        return country
    return None


def _print_tmdb_country_options(output_func=print) -> None:
    options = tmdb_country_options.country_options()
    parts = [
        f"{index}. {option['label']}"
        for index, option in enumerate(options, start=1)
    ]
    output_func("Список:")
    for start in range(0, len(parts), 5):
        output_func("; ".join(parts[start:start + 5]))


def request_tmdb_country_codes(input_func=input, output_func=print) -> list[str]:
    output_func("Введите номера стран, по которым будет производиться поиск:")
    _print_tmdb_country_options(output_func=output_func)
    while True:
        answer = input_func(">> ").strip()
        countries = tmdb_country_options.parse_country_indexes(answer)
        if countries is None or len(countries) == 0:
            output_func("Введите номера стран из списка через запятую, например: 1 или 1,2,3.")
            continue
        return countries


def _fit_title(title: str, width: int = 32) -> str:
    """Ограничивает ширину названия, чтобы строка Top-20 не переносилась в узкой консоли."""
    text = str(title or "Без названия")
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text.ljust(width)


def _print_tmdb_candidate_top(candidates: list, limit: int = 20) -> None:
    print("\nTop-20 TMDb candidate_pool:\n")
    for index, candidate in enumerate(candidates[:limit], start=1):
        final_score = float(candidate.get("final_score") or 0)
        country_score = float(candidate.get("country_score") or 0)
        print(
            f"{index:>2}. {_fit_title(candidate.get('title'))} | "
            f"final={final_score:.3f} | "
            f"country={country_score:.2f} | "
            f"TMDb={candidate.get('tmdb_score') or '-'}/{candidate.get('tmdb_votes') or 0}"
        )


def _print_tmdb_candidate_test_details(candidates: list, limit: int = 5) -> None:
    print("\nКандидаты test-run:\n")
    for index, candidate in enumerate(candidates[:limit], start=1):
        print(f"{index}. {candidate.get('title') or 'Без названия'}")
        print(f"   TMDb: {candidate.get('tmdb_score') or '-'} / {candidate.get('tmdb_votes') or 0}")
        print(f"   IMDb ID: {candidate.get('imdb_id') or '-'}")
        print(f"   signals: {', '.join(candidate.get('signals') or []) or 'нет'}\n")


def _print_tmdb_candidate_stats(result: dict) -> None:
    stats = result.get("stats") or {}
    print("\nСтатистика TMDb candidate_pool:")
    print(f"Источник: {stats.get('source', 'tmdb')} v{stats.get('source_version', 2)}")
    discover_filters = (result.get("settings") or {})
    print("TMDb Discover filters:")
    print(f"Минимальный год: {discover_filters.get('year_min') if discover_filters.get('year_min') is not None else 'не важно'}")
    print(f"Максимальный год: {discover_filters.get('year_max') if discover_filters.get('year_max') is not None else 'не важно'}")
    print(f"Минимальный TMDb рейтинг: {discover_filters.get('min_tmdb_score') if discover_filters.get('min_tmdb_score') is not None else 'не важно'}")
    print(f"Минимум голосов TMDb: {discover_filters.get('min_tmdb_votes') if discover_filters.get('min_tmdb_votes') is not None else 'не важно'}")
    print(f"Include жанры (TMDb): {tmdb_genre_options.describe_filter_value(discover_filters.get('with_genres'))}")
    print(f"Exclude жанры (TMDb): {tmdb_genre_options.describe_filter_value(discover_filters.get('without_genres'))}")
    print(f"Найдено через TMDb Discover: {stats.get('discover_total', 0)}")
    print(f"Удалено дублей: {stats.get('duplicates_removed', 0)}")
    print(f"Пропущено уже просмотренных: {stats.get('watched_skipped', 0)}")
    print(f"Пропущено уже в pool по TMDb ID: {stats.get('existing_pool_skipped_tmdb_id', 0)}")
    print(f"Пропущено уже в pool по title/year: {stats.get('existing_pool_skipped_title_year', 0)}")
    print(f"Запрошено TMDb Details: {stats.get('details_requested', 0)}")
    print(f"TMDb Details ошибок сети: {stats.get('details_errors', 0)}")
    print(f"С IMDb ID из TMDb external_ids: {stats.get('external_ids_imdb_id_count', 0)}")
    print(f"Complete кандидатов: {stats.get('complete_candidates', 0)}")
    print(f"С неполной TMDb/core metadata: {stats.get('incomplete_candidates', 0)}")
    print(f"Итоговых кандидатов: {stats.get('final_candidates', 0)}")


def _tmdb_mode_label(mode: str) -> str:
    labels = {
        "quality": "поиск по популярным",
        "hidden_gems": "поиск по недооценённым",
    }
    return labels.get(mode, mode)


def _parse_tmdb_genre_indexes(value: str, options: list[dict] | None = None) -> list[int] | None:
    text = str(value or "").strip()
    if text == "":
        return []
    options = options or tmdb_genre_options.TV_GENRE_OPTIONS
    indexes = []
    for part in text.replace(",", " ").split():
        try:
            index = int(part)
        except ValueError:
            return None
        if index < 1 or index > len(options):
            return None
        if index not in indexes:
            indexes.append(index)
    return indexes


def _print_tmdb_genre_options(options: list[dict], output_func=print) -> None:
    for index, option in enumerate(options, start=1):
        output_func(f" {index} >> {option['label']}")


def _input_tmdb_genre_ids(
    label: str,
    options: list[dict],
    *,
    allow_all: bool = False,
    input_func=input,
    output_func=print,
) -> list[int]:
    while True:
        answer = input_func(f"{label} [не важно] >> ").strip()
        if allow_all and answer.casefold() in {"все", "all", "*"}:
            return [int(option["id"]) for option in options]
        indexes = _parse_tmdb_genre_indexes(answer, options)
        if indexes is None:
            if allow_all:
                output_func("Введите номера жанров через запятую, например: 1,2,3, или все.")
            else:
                output_func("Введите номера жанров через запятую, например: 1,2,3")
            continue
        return tmdb_genre_options.genre_ids_from_indexes(indexes, options)


def _input_tmdb_include_mode(input_func=input, output_func=print) -> str:
    output_func("\nКак применять выбранные жанры (TMDb)?")
    output_func(" 1 >> Любой из выбранных жанров — шире поиск")
    output_func(" 2 >> Все выбранные жанры одновременно — строже поиск")
    while True:
        answer = input_func("Выбор [1] >> ").strip()
        if answer in {"", "1"}:
            return tmdb_genre_options.MODE_OR
        if answer == "2":
            return tmdb_genre_options.MODE_AND
        output_func("Выберите 1 или 2.")


def request_tmdb_discover_genre_filters(input_func=input, output_func=print) -> tuple[str | None, str | None]:
    output_func(f"\n{tmdb_genre_options.TMDB_DISCOVER_GENRE_TITLE}")
    output_func("Выбери жанры, которые должны попасть в поиск:")
    _print_tmdb_genre_options(tmdb_genre_options.INCLUDE_TV_GENRE_OPTIONS, output_func)
    output_func("\nВвод через запятую, например 1,2,3. Пустой ввод = не важно.")
    include_ids = _input_tmdb_genre_ids(
        "Include жанры",
        tmdb_genre_options.INCLUDE_TV_GENRE_OPTIONS,
        input_func=input_func,
        output_func=output_func,
    )

    include_mode = tmdb_genre_options.MODE_OR
    if len(include_ids) > 1:
        include_mode = _input_tmdb_include_mode(input_func=input_func, output_func=output_func)
    with_genres = tmdb_genre_options.build_filter_value(include_ids, mode=include_mode)
    include_labels = ", ".join(tmdb_genre_options.labels_from_ids(include_ids)) if include_ids else "без фильтра"
    mode_label = "любой из выбранных" if include_mode == tmdb_genre_options.MODE_OR else "все выбранные одновременно"
    output_func(f"Include жанры (TMDb): {include_labels}")
    if len(include_ids) > 1:
        output_func(f"Режим: {mode_label}")

    output_func(f"\n{tmdb_genre_options.TMDB_EXCLUDE_LABEL}")
    output_func("Выбери жанры, которые нужно исключить:")
    output_func(" все >> все перечисленные exclude-жанры")
    _print_tmdb_genre_options(tmdb_genre_options.EXCLUDE_TV_GENRE_OPTIONS, output_func)
    output_func("\nВвод через запятую, например 1,2,3,4. Пустой ввод = не важно. Можно ввести все.")
    exclude_ids = _input_tmdb_genre_ids(
        "Exclude жанры",
        tmdb_genre_options.EXCLUDE_TV_GENRE_OPTIONS,
        allow_all=True,
        input_func=input_func,
        output_func=output_func,
    )
    without_genres = tmdb_genre_options.build_filter_value(exclude_ids, mode=tmdb_genre_options.MODE_OR)
    exclude_labels = ", ".join(tmdb_genre_options.labels_from_ids(exclude_ids)) if exclude_ids else "без фильтра"
    output_func(f"Exclude жанры (TMDb): {exclude_labels}")
    return with_genres, without_genres


def ask_auto_import_choice(input_func=input, output_func=print) -> bool:
    """Спрашивает, нужно ли сразу импортировать TMDb result в общий пул."""
    while True:
        answer = str(
            input_func("Импортировать результат в общий пул кандидатов? [Y/n] >> ")
        ).strip().casefold()
        if answer in {"", "y", "yes", "д", "да"}:
            return True
        if answer in {"n", "no", "н"}:
            return False
        output_func("Неверный ввод. Используйте Enter/Y для импорта или N для отмены.")


def _print_tmdb_import_stats(stats: dict, output_func=print) -> None:
    """Печатает статистику импорта TMDb result в общий candidate pool."""
    skipped_watched = stats.get("skipped_watched", stats.get("watched_skipped", 0))
    skipped_duplicates = stats.get("skipped_duplicates", stats.get("duplicates", 0))

    output_func(f"Прочитано: {stats.get('read', 0)}")
    output_func(f"Добавлено новых: {stats.get('added', 0)}")
    output_func(f"Обновлено существующих: {stats.get('updated', 0)}")
    output_func(f"Пропущено already watched: {skipped_watched}")
    output_func(f"Пропущено как дубли: {skipped_duplicates}")
    output_func(f"Ошибок: {stats.get('errors', 0)}")
    output_func(f"Размер пула до импорта: {stats.get('pool_size_before', 0)}")
    output_func(f"Размер пула после импорта: {stats.get('pool_size_after', stats.get('pool_size', 0))}")
    output_func(f"criteria_name: {stats.get('criteria_name') or '-'}")


def maybe_auto_import_tmdb_result(
    result_path,
    criteria_name: str,
    *,
    input_func=input,
    output_func=print,
    import_func=None,
):
    """Предлагает авто-импорт сохранённого TMDb result в общий candidate pool."""
    if ask_auto_import_choice(input_func=input_func, output_func=output_func) is False:
        output_func("Импорт отменён. Result сохранён, его можно импортировать позже через управление пуллами.")
        return None

    if import_func is None:
        def import_func(result_path, criteria_name=None):
            return candidate_service.import_tmdb_result_to_pool(result_path, criteria_name=criteria_name)

    try:
        import_result = import_func(result_path, criteria_name=criteria_name)
    except Exception as error:
        output_func(f"Авто-импорт не выполнен: {error}")
        output_func("Result сохранён, его можно импортировать позже через управление пуллами.")
        return None

    if isinstance(import_result, dict) and "stats" in import_result:
        if import_result.get("ok") is False:
            error_text = import_result.get("error") or "неизвестная ошибка"
            output_func(f"Авто-импорт не выполнен: {error_text}")
            output_func("Result сохранён, его можно импортировать позже через управление пуллами.")
            return import_result
        stats = import_result["stats"]
    else:
        stats = import_result

    if isinstance(stats, dict) is False or stats.get("ok") is False:
        error_text = stats.get("error") if isinstance(stats, dict) else "неизвестная ошибка"
        output_func(f"Авто-импорт не выполнен: {error_text}")
        output_func("Result сохранён, его можно импортировать позже через управление пуллами.")
        return stats

    output_func("\nИмпорт TMDb result завершён.")
    _print_tmdb_import_stats(stats, output_func=output_func)
    return stats


def run_tmdb_candidate_pool_flow(is_test_run: bool = False) -> None:
    """Запускает новый TMDb-only candidate_pool v2."""
    from candidates.models.keys import COMMON_POOL_CRITERIA_NAME

    ui.clean_terminal()
    print("TMDb candidate_pool v2\n")
    country_codes = request_tmdb_country_codes(input_func=input, output_func=print)
    if len(country_codes) > 1:
        print("Пока один запуск TMDb candidate_pool поддерживает одну страну. Выберите один номер.")
        return
    country = country_codes[0]

    print("\nРежим:")
    print("1 >> Поиск по популярным")
    print("2 >> Поиск по недооценённым")
    mode_answer = input("Выбор [1] >> ").strip()
    if mode_answer in ("", "1"):
        mode = "quality"
    elif mode_answer == "2":
        mode = "hidden_gems"
    else:
        print("Ошибка: выберите 1 или 2.")
        return

    if is_test_run:
        pages = 1
        details_answer = input("\nСколько кандидатов детально обработать в test-run [5] >> ").strip()
        details_limit = _parse_bounded_int(details_answer, default=5, min_value=1, max_value=300)
    else:
        pages_answer = input("\nСколько страниц TMDb Discover? По умолчанию 3: ").strip()
        pages = _parse_bounded_int(pages_answer, default=3, min_value=1, max_value=20)
        details_answer = input("Сколько кандидатов отправить в TMDb Details? По умолчанию 50: ").strip()
        details_limit = _parse_bounded_int(details_answer, default=50, min_value=1, max_value=300)

    year_min = _parse_optional_bounded_int(input("\nМинимальный год [не важно] >> ").strip(), 1900, constant.NOW_YEAR)
    year_max = _parse_optional_bounded_int(input("Максимальный год [не важно] >> ").strip(), 1900, constant.NOW_YEAR)
    min_tmdb_score = _parse_optional_bounded_float(input("Минимальный TMDb рейтинг [не важно] >> ").strip(), 0.0, 10.0)
    min_tmdb_votes = _parse_optional_bounded_int(input("Минимум голосов TMDb [не важно] >> ").strip(), 0, 10_000_000)
    with_genres, without_genres = request_tmdb_discover_genre_filters(input_func=input, output_func=print)
    criteria_name = COMMON_POOL_CRITERIA_NAME

    print("\nБудет запущен TMDb-only candidate_pool v2:\n")
    print("Обновление общего pool")
    print(f"Страна: {country}")
    print(f"Режим: {_tmdb_mode_label(mode)}")
    if is_test_run:
        print("Режим запуска: тестовый прогон")
    print(f"Страниц TMDb Discover: {pages}")
    print(f"Лимит TMDb Details: {details_limit}")
    print(f"Минимальный год: {year_min if year_min is not None else 'не важно'}")
    print(f"Максимальный год: {year_max if year_max is not None else 'не важно'}")
    print(f"Минимальный TMDb рейтинг: {min_tmdb_score if min_tmdb_score is not None else 'не важно'}")
    print(f"Минимум голосов TMDb: {min_tmdb_votes if min_tmdb_votes is not None else 'не важно'}")
    print(f"Include жанры (TMDb): {tmdb_genre_options.describe_filter_value(with_genres)}")
    print(f"Exclude жанры (TMDb): {tmdb_genre_options.describe_filter_value(without_genres)}")
    if is_test_run:
        print("\nПлан тестового режима:")
        print(f"Лимит TMDb Details: {details_limit}")
        print(f"Будет детально обработано не больше {details_limit} кандидатов.")
        print("Основной candidate_pool_RU_quality.json не будет перезаписан.")

    confirmation = input("\nПродолжить? [y/N]: ").strip().casefold()
    if confirmation not in {"y", "yes", "д", "да"}:
        print("Операция отменена.")
        return

    try:
        result = candidate_service.build_tmdb_candidate_pool(
            country=country,
            pages=pages,
            details_limit=details_limit,
            mode=mode,
            criteria_name=criteria_name,
            year_min=year_min,
            year_max=year_max,
            min_tmdb_score=min_tmdb_score,
            min_tmdb_votes=min_tmdb_votes,
            with_genres=with_genres,
            without_genres=without_genres,
        )
        if is_test_run:
            print("Сохранение test candidate_pool: Ожидание")
            save_result = candidate_service.save_tmdb_build_result(result, is_test_run=True)
            print("Сохранение test candidate_pool: Успешно")
        else:
            print("Сохранение candidate_pool: Ожидание")
            save_result = candidate_service.save_tmdb_build_result(result, is_test_run=False)
            print("Сохранение candidate_pool: Успешно")
        json_path = save_result["json_path"]
        csv_path = save_result["csv_path"]
    except RuntimeError as error:
        text = str(error)
        if "TMDB_TOKEN" in text:
            print("Ошибка: не найден TMDB_TOKEN. Проверь .env / переменные окружения.")
        elif "TMDB" in text or "getaddrinfo" in text or "подключиться" in text:
            print("Ошибка доступа к TMDb. Если кэш есть, проверь, может ли генератор работать из кэша.")
            print(text)
        else:
            print(f"Ошибка: {text}")
        return
    except OSError as error:
        print(f"Ошибка файловой системы: {error}")
        return

    if is_test_run:
        print("\nТестовый прогон завершён.")
        print(f"Основной candidate_pool_{country}_{mode}.json не изменялся.")
        print(f"Файл тестового результата: {json_path}")
        stats = result.get("stats") or {}
        print("\nТестовый режим:")
        print(f"Найдено через TMDb Discover: {stats.get('discover_total', 0)}")
        print(f"Лимит TMDb Details: {details_limit}")
        print(f"Будет детально обработано не больше {details_limit} кандидатов.")
    else:
        print("\nTMDb candidate_pool v2 готов.")
    if is_test_run is False:
        print(f"TMDb result сохранён: {json_path}")
        maybe_auto_import_tmdb_result(json_path, criteria_name)
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    _print_tmdb_candidate_stats(result)

    candidates = result.get("candidates") or []
    if len(candidates) > 0:
        if is_test_run:
            _print_tmdb_candidate_test_details(candidates)
        else:
            _print_tmdb_candidate_top(candidates)
    else:
        print("Итоговый список кандидатов пуст.")


def show_tmdb_dataset_genre_diagnostics() -> None:
    """Показывает и сохраняет распределение TMDb TV-жанров по текущему dataset."""
    from candidates.sources.tmdb.builder import (
        build_tmdb_genre_distribution_report,
        save_tmdb_genre_distribution_report,
    )

    ui.clean_terminal()
    dataset = storage_data.load_dataset()
    meta = storage_data.load_meta()
    if len(dataset) == 0:
        print("Dataset пуст. Диагностика жанров недоступна.")
        return

    print("TMDb genre distribution for dataset:\n")
    print("Будут выполнены TMDb details/search запросы с использованием локального кэша, если он есть.")
    answer = input("Продолжить? [y/N] ").strip().casefold()
    if answer not in {"y", "yes", "д", "да"}:
        print("Операция отменена.")
        return

    def print_progress(event: dict) -> None:
        index = event.get("index")
        total = event.get("total")
        title = event.get("title") or "-"
        year = event.get("year") or "-"
        status = event.get("status")
        if status == "start":
            print(f"[{index}/{total}] {title} ({year}): поиск TMDb...")
            return

        if status == "matched":
            genres = ", ".join(event.get("genres") or []) or "жанры пустые"
            print(f"[{index}/{total}] {title} ({year}): найдено, жанры={genres}")
        elif status == "error":
            print(f"[{index}/{total}] {title} ({year}): ошибка {event.get('error')}")
        elif status == "stopped":
            print(f"\n{event.get('error')}")
            print("Проверьте доступ к TMDb/VPN/сеть и запустите диагностику позже.")
        else:
            print(f"[{index}/{total}] {title} ({year}): не найдено")

    try:
        report = build_tmdb_genre_distribution_report(dataset, meta, progress_callback=print_progress)
        report_path = save_tmdb_genre_distribution_report(report)
    except RuntimeError as error:
        print(f"Ошибка TMDb: {error}")
        return
    except OSError as error:
        print(f"Ошибка файловой системы: {error}")
        return

    print("\nTMDb genre distribution for dataset:\n")
    if report["genre_counts"]:
        for genre_name, count in report["genre_counts"].items():
            print(f"{genre_name}: {count}")
    else:
        print("Жанры не найдены.")

    print("\nИтог:")
    print(f"Обработано записей: {report['total_dataset_items']}")
    print(f"Фактически проверено: {report.get('processed', report['total_dataset_items'])}")
    print(f"Найдено в TMDb: {report['matched']}")
    print(f"Не найдено: {report['unmatched']}")
    print(f"Без жанров: {len(report.get('empty_genre_items') or [])}")
    if report.get("stopped_early"):
        print(f"Остановлено досрочно: {report.get('stop_reason')}")

    if report["unmatched_items"]:
        print("\nНе найдено:")
        for item in report["unmatched_items"]:
            year = item.get("year") or "-"
            print(f"- {item.get('title')} ({year})")

    if report.get("empty_genre_items"):
        print("\nTMDb найден, но genres пустые:")
        for item in report["empty_genre_items"]:
            year = item.get("year") or "-"
            print(f"- {item.get('title')} ({year})")

    print(f"\nОтчёт сохранён: {report_path}")


def import_tmdb_result_to_common_pool_flow() -> None:
    """Импортирует отдельный TMDb v1 result JSON в общий candidate_pool после подтверждения."""
    ui.clean_terminal()
    files_view = candidate_service.get_tmdb_import_files_view()
    if files_view["is_empty"]:
        print("TMDb result JSON в data/candidate_pool не найдены.")
        return

    files = files_view["files"]
    print("TMDb result JSON:\n")
    for index, path in enumerate(files, start=1):
        print(f"{index} >> {path.name}")

    selected = request.loop_input(
        text="\nВыберите файл для импорта >> ",
        funcs_list=[lambda value: value.isdigit() and 1 <= int(value) <= len(files)]
    )
    result_path = files[int(selected) - 1]

    preview = candidate_service.load_tmdb_result_import_preview(result_path)
    if preview["ok"] is False:
        print(f"Не удалось прочитать файл: {preview.get('error')}")
        return

    print("\nPreview импорта TMDb result:")
    print(f"Файл: {result_path}")
    print(f"Кандидатов в файле: {preview['candidate_count']}")
    print("Будет добавлено/обновлено в общий pool после дедупликации.")
    print("Источник: tmdb_imdb_kp_v1")

    answer = input("\nИмпортировать в общий candidate_pool? [y/N] ").strip().casefold()
    if answer not in {"y", "yes", "д", "да"}:
        print("Импорт отменён.")
        return

    import_result = candidate_service.import_tmdb_result_to_pool(result_path)
    if import_result["ok"] is False:
        print(f"Импорт не выполнен: {import_result.get('error')}")
        return

    stats = import_result["stats"]
    print("\nИмпорт TMDb result завершён.")
    print(f"Прочитано: {stats['read']}")
    print(f"Добавлено новых: {stats['added']}")
    print(f"Обновлено существующих: {stats['updated']}")
    print(f"Пропущено already watched: {stats['watched_skipped']}")
    print(f"Пропущено как дубли: {stats['duplicates']}")
    print(f"Ошибок: {stats['errors']}")
    print(f"Текущий размер общего пула: {stats.get('pool_size', 0)}")
