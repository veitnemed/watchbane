"""Содержит действия интерфейса, которые запускаются из пунктов меню."""

import json
import time
from pathlib import Path

from config import constant
from candidates import country_schema
from candidates import genre_schema
from candidates import service as candidate_service
from candidates import tmdb_country_options
from candidates import tmdb_genre_options
from dataset import dataset_stats
from dataset import delete_record as dataset_delete_record
from dataset import genre_import
from dataset import genre_stats
from apis import imdb_sql as sql_search
from dataset import title_resolve
from posters.download_images import PREVIEW_BATCH_SIZE, PREVIEW_BULK_DELAY_SECONDS, PREVIEW_DOWNLOAD_SIZE
from ui.console import candidate_pool_ui
from ui.console import request
from ui.console import title_presenters
from storage import data as storage_data
from dataset import storage_movie
from ui.console import ui
from common import valid


def _parse_user_score(value) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def show_all_movies():
    """Показывает все фильмы из датасета."""
    data = storage_data.load_dataset()
    if len(data) == 0:
        print('Датасет пуст!')
        return

    rows = _build_sorted_score_rows(data)
    for idx, row in enumerate(rows, start=1):
        year_text = f" | год: {row['year']}" if row.get("year") not in (None, "") else ""
        print(f"{idx}) {row['title']} | user_score: {row['score']}{year_text}")


def request_object() -> None:
    """Запрашивает фильм и добавляет его в датасет."""
    ui.clean_terminal()

    defaults, meta_payload, poster_hints = request.request_api_defaults(confirm_genres=True)
    if defaults is None:
        return

    movie_request = request.request_all_scores(defaults)
    result = storage_movie.add_movie(
        movie_request,
        meta_payload=meta_payload,
        poster_hints=poster_hints,
        print_message=False,
    )
    print(result.message)


def print_candidate_genre_transfer_preview(preview: dict) -> None:
    """Печатает read-only preview жанров перед переносом candidate -> dataset."""
    print("Жанры для переноса в dataset:")

    genre_keys = preview.get("genre_keys") or []
    if len(genre_keys) > 0:
        print(f"  Pool genre_keys: {', '.join(genre_keys)}")
    else:
        print("  Pool genre_keys: нет")

    active_labels = preview.get("active_has_labels") or []
    if len(active_labels) > 0:
        print(f"  Будут выставлены: {', '.join(active_labels)}")
    else:
        print("  Активные жанры dataset: нет")

    if preview.get("used_fallback"):
        print("  Источник: fallback по raw genres")

    if preview.get("mapper_status") == "partial":
        unmapped_keys = preview.get("unmapped_genre_keys") or []
        if len(unmapped_keys) > 0:
            print(f"  Не удалось сопоставить: {', '.join(unmapped_keys)}")

    if preview.get("warn_all_genres_zero"):
        print("  Внимание: у кандидата есть raw-жанры, но ни один не попал в has_* dataset.")
        print("  Проверь жанры вручную в форме.")

    print("")


def mark_candidate_as_watched() -> None:
    """Переносит кандидата из пула в основной датасет через обычный сценарий добавления."""
    ui.clean_terminal()
    watched_view = candidate_service.get_mark_watched_view()
    candidates = watched_view["candidates"]
    criteria_view = candidate_service.get_common_pool_criteria_view()
    criteria = criteria_view.get("criteria") or {}

    print("\nОбщий пул кандидатов")
    print(f"Страна: {criteria.get('country') or 'не важно'}")
    for line in watched_view["lines"]:
        print(line)
    print("")

    if len(candidates) == 0:
        print("В общем pool кандидатов пока нет.")
        return

    for idx, candidate in enumerate(candidates, start=1):
        title = candidate.get("title") or "Без названия"
        year = candidate.get("year") or "?"
        description = request.short_text(
            candidate.get("description") or candidate.get("overview"),
            50,
        ) or "без описания"
        poster_url = candidate.get("poster_url")
        poster_label = request.short_text(poster_url, 60) if poster_url else "без постера"
        print(f"{idx}) {title} ({year})")
        print(f"   Описание: {description}")
        print(f"   Постер: {poster_label}")

    selected_index = request.loop_input(
        text="\nНомер просмотренного кандидата >> ",
        funcs_list=[lambda value: value.isdigit() and 1 <= int(value) <= len(candidates)]
    )
    candidate = candidates[int(selected_index) - 1]

    print("")
    transfer_payload = title_resolve.build_candidate_transfer_payload(candidate)
    defaults = transfer_payload["defaults"]
    meta_payload = transfer_payload["meta_payload"]
    if candidate_service.is_pool_candidate_incomplete(candidate):
        print("Кандидат неполный: нет KP/IMDb данных.")
        print("Можно продолжить вручную, но проверь raw_scores.\n")
    print_candidate_genre_transfer_preview(
        title_resolve.build_candidate_genre_transfer_preview(candidate)
    )
    movie_request = request.request_all_scores(defaults)
    result = storage_movie.add_movie(
        movie_request,
        meta_payload=meta_payload,
        pool_candidate=candidate,
        print_message=False,
    )
    print(result.message)


def show_data_info():
    """Показывает сводку по датасету."""
    data = storage_data.load_dataset()
    for line in dataset_stats.build_dataset_info_lines(data):
        print(line)


def rename_movie_record() -> None:
    """Переименовывает запись в основном датасете и meta."""
    ui.clean_terminal()
    titles = storage_data.get_all_titles()
    if len(titles) == 0:
        print("Датасет пуст!")
        return

    print("Текущие записи:\n")
    for idx, title in enumerate(titles, start=1):
        print(f"{idx}) {title}")

    old_title = request.loop_input(
        text="\nСтарое название >> ",
        funcs_list=[valid.is_correct_title]
    )
    new_title = request.loop_input(
        text="Новое название >> ",
        funcs_list=[valid.is_correct_title]
    )

    if storage_data.rename_movie_title(old_title, new_title):
        print("Название записи обновлено.")
    else:
        print("Переименование не выполнено.")


def delete_watched_record() -> None:
    """Safely deletes one watched record from dataset, meta and poster-cache."""
    ui.clean_terminal()
    data = storage_data.load_dataset()
    if len(data) == 0:
        print("Датасет пуст!")
        return

    query = input("\nПоиск записи по названию >> ").strip()
    if query == "":
        print("Поиск отменён: пустой запрос.")
        return

    matches = dataset_delete_record.search_watched_records_by_query(query, data=data)
    if len(matches) == 0:
        print("Запись не найдена.")
        return

    selected = matches[0]
    if len(matches) > 1:
        print("\nНайдено несколько записей:\n")
        for index, item in enumerate(matches, start=1):
            year_label = item.get("year") if item.get("year") not in (None, "") else "—"
            score_label = item.get("user_score") if item.get("user_score") is not None else "—"
            print(f"  {index}) {item['title']} ({year_label}) · оценка {score_label}")

        while True:
            answer = input("\nВыберите номер записи >> ").strip()
            if answer.isdigit() is False:
                print("Введите номер из списка.")
                continue
            choice = int(answer)
            if choice < 1 or choice > len(matches):
                print("Введите номер из списка.")
                continue
            selected = matches[choice - 1]
            break

    preview = dataset_delete_record.build_watched_delete_preview(selected["dataset_key"], data=data)
    if preview is None:
        print("Запись не найдена.")
        return

    print()
    print(dataset_delete_record.format_watched_delete_preview(preview))
    print()
    confirmation = input("Введите DELETE для удаления: ").strip()
    if confirmation != "DELETE":
        print("Удаление отменено.")
        return

    result = dataset_delete_record.delete_watched_record(selected["dataset_key"])
    print()
    print(dataset_delete_record.format_watched_delete_report(result))
    if result.get("ok") is False:
        print("Данные не изменены.")


def load_genre_markup():
    """Загружает жанровую разметку для текущего датасета с подтверждением."""
    ui.clean_terminal()
    result = genre_import.apply_genre_markup()
    print(f"\nОбработано записей: {result['total']}")
    print(f"Подтверждено: {result['updated']}")
    print(f"Пропущено: {result['skipped']}")
    print(f"Не найдено: {len(result['not_found'])}")
    print(f"Ошибок API: {len(result['errors'])}")


def show_api_features():
    """Ищет сериал через API и печатает полный JSON найденного объекта."""
    title = request.loop_input(
        text='Название сериала >> ',
        funcs_list=[valid.is_correct_title]
    )
    result = title_resolve.fetch_series_raw(title, "Россия")

    if result["ok"] is False:
        print(f'Сериал не найден в списке API: {result["details"]}')
        return

    print('\nСериал найден в списке API.\n')
    for line in title_resolve.format_series_lines(result["data"]):
        print(line)


def _print_api_ping_result(name: str, host: str, result: dict, elapsed_ms: float | None = None) -> None:
    print(f"{name} ({host})")
    if result.get("ok") is True:
        ms = elapsed_ms if elapsed_ms is not None else result.get("elapsed_ms")
        status_line = "  Статус: OK"
        if ms is not None:
            status_line += f" ({ms} мс)"
        print(status_line)
    else:
        print("  Статус: Ошибка")
        details = result.get("details") or result.get("error") or "unknown_error"
        print(f"  Причина: {details}")
    print()


def ping_external_apis() -> None:
    """Проверяет доступность Kinopoisk и TMDb API короткими запросами."""
    from apis import kp_api
    from apis import tmdb_api

    print("Пинг внешних API...\n")

    started = time.monotonic()
    kp_result = kp_api.check_api_available()
    kp_ms = round((time.monotonic() - started) * 1000, 1)
    _print_api_ping_result("Kinopoisk API", "api.kinopoisk.dev", kp_result, kp_ms)

    started = time.monotonic()
    tmdb_result = tmdb_api.check_api_available()
    tmdb_ms = round((time.monotonic() - started) * 1000, 1)
    _print_api_ping_result("TMDb API", "api.themoviedb.org", tmdb_result, tmdb_ms)


def print_sql_title_result(data: dict) -> None:
    """Печатает компактную карточку результата SQL-поиска."""
    title_presenters.print_sql_title_result(data)


def search_sql_title_by_name() -> None:
    """Ищет тайтл в локальной SQLite-базе IMDb по названию."""
    title = request.loop_input(
        text="Название >> ",
        funcs_list=[lambda value: str(value).strip() != ""]
    )
    country = request.loop_input_with_default(
        text="Страна [Россия] >> ",
        funcs_list=[lambda value: str(value).strip() != ""],
        default_value="Россия"
    )
    result = sql_search.search_title_in_sql(title, country)

    if result["ok"] is False:
        print(f"Тайтл не найден: {result['details'] or result['error']}")
        return

    print_sql_title_result(result["data"])


def sync_watched_descriptions_and_posters() -> None:
    """Backfills meta descriptions and poster-cache for watched dataset records."""
    from posters.sync_watched import sync_watched_metadata

    print("Обновление описаний и poster-cache для просмотренных...\n")

    def progress(current: int, total: int, title: str) -> None:
        print(f"{current}/{total} | {title}")

    stats = sync_watched_metadata(write_meta=True, progress_callback=progress)
    print("\nИтог:")
    print(f"  Записей: {stats['total']}")
    print(f"  Описаний найдено: {stats['description_found']}")
    print(f"  Описаний записано в meta: {stats['description_updated']}")
    print(f"  Poster found: {stats['poster_found']}")
    print(f"  Poster missing: {stats['poster_missing']}")


def fetch_tmdb_poster_metadata() -> None:
    """Fetches missing poster metadata from TMDb cache/API into poster-cache."""
    from posters.fetch_metadata import fetch_poster_metadata_for_watched

    print("Загрузка poster metadata из TMDb...\n")

    def progress(current: int, total: int, title: str) -> None:
        print(f"{current}/{total} | {title}")

    stats = fetch_poster_metadata_for_watched(use_api=True, progress_callback=progress)
    print("\nИтог:")
    print(f"  Записей dataset: {stats['total']}")
    print(f"  Уже было poster: {stats['skipped_found']}")
    print(f"  Обновлено из TMDb cache: {stats['updated_from_cache']}")
    print(f"  Обновлено через TMDb API: {stats['updated_from_api']}")
    print(f"  Без tmdb_id: {stats['missing_tmdb_id']}")
    print(f"  Всё ещё missing: {stats['still_missing']}")


def download_poster_images_local() -> None:
    """Downloads poster images for poster-cache entries with poster_url."""
    from posters.download_images import download_poster_images

    print("Скачивание poster images в data/cache/posters/images/...\n")

    def progress(current: int, total: int, title: str) -> None:
        print(f"{current}/{total} | {title}")

    stats = download_poster_images(progress_callback=progress)
    print("\nИтог:")
    print(f"  Записей в cache: {stats['total_entries']}")
    print(f"  Кандидатов на скачивание: {stats['candidates']}")
    print(f"  Скачано: {stats['downloaded']}")
    print(f"  Уже были локально: {stats['skipped_existing']}")
    print(f"  Ошибок: {stats['failed']}")


def fetch_watched_tmdb_metadata() -> None:
    """Loads TMDb metadata for watched records by title + year."""
    from posters.fetch_watched_tmdb import (
        fetch_watched_tmdb_metadata as run_fetch,
        format_watched_tmdb_unresolved_report,
    )

    print("Загрузка TMDb metadata для просмотренных...\n")

    def progress(current: int, total: int, title: str) -> None:
        print(f"{current}/{total} | {title}")

    stats = run_fetch(progress_callback=progress)
    print("\nИтог:")
    print(f"  Проверено записей: {stats['checked']}")
    print(f"  Уже были tmdb_id: {stats['already_had_tmdb_id']}")
    print(f"  Найдено tmdb_id: {stats['found_tmdb_id']}")
    print(f"  Добавлено description: {stats['added_description']}")
    print(f"  Добавлено poster_url: {stats['added_poster_url']}")
    print(f"  Обновлено poster-cache: {stats['poster_cache_updated']}")
    print(f"  Manual overrides успешно: {stats['manual_overrides_used']}")
    print(f"  Manual overrides ошибка: {stats['manual_overrides_failed']}")
    print(f"  Пропущено, не найдено: {stats['skipped_not_found']}")
    print(f"  Пропущено, сомнительный match: {stats['skipped_uncertain_match']}")
    print(f"  Ошибки сети: {stats['network_errors']}")
    print()
    print(format_watched_tmdb_unresolved_report(stats.get("unresolved") or []))


def diagnose_unresolved_watched_tmdb_metadata() -> None:
    """Print read-only diagnostics for unresolved watched TMDb metadata."""
    from posters.tmdb_diagnostic import (
        diagnose_watched_tmdb_unresolved,
        format_watched_tmdb_diagnostic_report,
    )

    print("Диагностика unresolved TMDb metadata (read-only)...\n")

    def progress(current: int, total: int, title: str) -> None:
        print(f"{current}/{total} | {title}")

    report = diagnose_watched_tmdb_unresolved(progress_callback=progress)
    print()
    print(format_watched_tmdb_diagnostic_report(report))


def show_dataset_genres() -> None:
    """Показывает все жанры текущего датасета через API."""
    ui.clean_terminal()
    genre_stats.show_dataset_genres()


def collect_candidate_pool() -> None:
    """Собирает кандидатов в общий pool по сохранённым настройкам (legacy KP API)."""
    ui.clean_terminal()
    selected = candidate_pool_ui.choose_or_create_criteria()
    if selected is None:
        print("Настройки сбора не заданы.")
        return

    criteria_name, criteria = selected
    print(f"\nЗапуск подбора в общий pool")
    result = candidate_service.collect_candidates_legacy(criteria_name, criteria)

    print("\nСбор в общий pool завершён.")
    print(f"Нужно было собрать: {result['target_count']}")
    print(f"Новых кандидатов добавлено: {result['added']}")
    print(f"Совпадений уже в JSON: {result['duplicates']}")
    print(f"Уже есть в основном датасете: {result['watched_skipped']}")
    print(f"Проверено объектов API: {result['scanned']}")
    print(f"Последняя страница: {result['last_page']}")
    print(f"Текущий размер пула: {result['pool_size']}")

    if result.get("api_unavailable"):
        print("API сейчас недоступен. Общий пул сохранён без изменений.")

    if result["reached_end"]:
        print("Выдача API закончилась раньше, чем набралось нужное количество.")

    if len(result["errors"]) > 0:
        print("Ошибки API/сети:")
        for error in result["errors"]:
            print(f"- {error}")


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
            f"TMDb={candidate.get('tmdb_rating') or '-'}/{candidate.get('tmdb_votes') or 0} | "
            f"IMDb={candidate.get('imdb_rating') or '-'}/{candidate.get('imdb_votes') or 0}"
        )


def _print_tmdb_candidate_test_details(candidates: list, limit: int = 5) -> None:
    print("\nКандидаты test-run:\n")
    for index, candidate in enumerate(candidates[:limit], start=1):
        print(f"{index}. {candidate.get('title') or 'Без названия'}")
        print(f"   TMDb: {candidate.get('tmdb_score') or candidate.get('tmdb_rating') or '-'} / {candidate.get('tmdb_votes') or 0}")
        print(f"   IMDb: {candidate.get('imdb_score') or candidate.get('imdb_rating') or '-'} / {candidate.get('imdb_votes') or 0}")
        print(f"   KP: {candidate.get('kp_status') or 'not_requested'}")
        print(f"   KP score: {candidate.get('kp_score') or candidate.get('kp_rating') or '-'} / {candidate.get('kp_votes') or 0}")
        print(f"   signals: {', '.join(candidate.get('signals') or []) or 'нет'}\n")


def _print_tmdb_candidate_stats(result: dict) -> None:
    stats = result.get("stats") or {}
    discover_filters = stats.get("discover_filters") or {}
    print("\nСтатистика TMDb candidate_pool:")
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
    print(f"Запрошено TMDb Details: {stats.get('details_requested', 0)}")
    print(f"TMDb Details ошибок сети: {stats.get('tmdb_details_errors', 0)}")
    print(f"TMDb Details пропущено после ошибок: {stats.get('tmdb_details_skipped_after_errors', 0)}")
    print(f"С IMDb ID: {stats.get('has_imdb_id', 0)}")
    print(f"Найдено в IMDb dataset: {stats.get('found_in_imdb_sql', 0)}")
    print(f"KP найдено в кэше: {stats.get('kp_cache_hit', 0)}")
    print(f"KP API запросов: {stats.get('kp_api_requested', 0)}")
    print(f"KP API найдено: {stats.get('kp_api_found', 0)}")
    print(f"KP API не найдено: {stats.get('kp_api_not_found', 0)}")
    print(f"KP API отклонено match-check: {stats.get('kp_api_rejected_by_match', 0)}")
    print(f"KP API ошибок: {stats.get('kp_api_errors', 0)}")
    print(f"KP API пропущено после ошибок: {stats.get('kp_api_skipped_after_errors', 0)}")
    print(f"KP API пропущено из-за кэша: {stats.get('kp_api_skipped_cache', 0)}")
    print(f"KP ожидает добора из-за лимита: {stats.get('kp_pending_limit', 0)}")
    print(f"Неполных кандидатов по KP: {stats.get('kp_incomplete_candidates', 0)}")
    print(f"Полностью обогащённых кандидатов: {stats.get('complete_candidates', 0)}")
    print(f"Прошли country_score: {stats.get('country_passed', 0)}")
    print(f"Отклонено adult/titleType: {stats.get('adult_title_type_rejected', 0)}")
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
    """Запускает новый TMDb candidate_pool v1 без смешивания со старым общим пулом."""
    from pathlib import Path

    from apis import imdb_sql as sql_search

    from candidates.keys import COMMON_POOL_CRITERIA_NAME

    ui.clean_terminal()
    print("TMDb candidate_pool v1\n")
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

    print("\nБудет запущен TMDb candidate_pool v1:\n")
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
    print("KP API: включён после локального KP cache, при ошибке сбор продолжается без KP.")
    if is_test_run:
        print("\nПлан тестового режима:")
        print(f"Лимит TMDb Details: {details_limit}")
        print(f"Будет детально обработано не больше {details_limit} кандидатов.")
        print("Основной candidate_pool_RU_quality.json не будет перезаписан.")

    confirmation = input("\nПродолжить? [y/N]: ").strip().casefold()
    if confirmation not in {"y", "yes", "д", "да"}:
        print("Операция отменена.")
        return

    if Path(sql_search.DEFAULT_DB_PATH).is_file() is False:
        print("Ошибка: не найдена локальная IMDb SQLite база. Проверь путь в настройках.")
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
        print("\nTMDb candidate_pool v1 готов.")
    if is_test_run is False:
        print(f"TMDb result сохранён: {json_path}")
        maybe_auto_import_tmdb_result(json_path, criteria_name)
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    _print_tmdb_candidate_stats(result)

    kp_debug = result.get("kp_debug")
    if isinstance(kp_debug, dict):
        from candidates import kp_tmdb_build_debug

        for line in kp_tmdb_build_debug.format_kp_debug_lines(kp_debug):
            print(line)
        debug_path = json_path.with_name(f"{json_path.stem}_kp_debug.json")
        if debug_path.is_file():
            print(f"KP debug JSON: {debug_path}")

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
    from candidates.tmdb_candidate_pool import (
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


def edit_candidate_pool_filters() -> None:
    """Обновляет saved defaults фильтров поиска для общего pool."""
    ui.clean_terminal()
    criteria_view = candidate_service.get_common_pool_criteria_view()
    if criteria_view["has_criteria"] is False:
        criteria_name, criteria = candidate_service.ensure_common_pool_criteria()
    else:
        criteria_name = criteria_view["criteria_name"]
        criteria = criteria_view["criteria"]

    print("\nDefaults фильтров поиска для общего pool")
    print("Жанры берутся из сохранённых кандидатов pool. Это не запускает TMDb Discover.")
    print(f"Текущий KP: {criteria.get('min_kp', 'не важно')}")
    print(f"Текущие жанры (saved pool): {', '.join(criteria.get('genres', [])) or 'не важно'}")
    print(f"Исключить жанры (saved pool): {', '.join(criteria.get('excluded_genres', [])) or 'не важно'}\n")

    updated = candidate_pool_ui.update_criteria_filters(criteria_name, criteria)
    print("\nDefaults обновлены в candidate_criteria.json.")
    print("Filters сохраняются как defaults поиска по уже сохранённым кандидатам (Enter = default).")
    print("Ручной ввод в поиске действует только на текущий запуск.")
    print("Filters не пересобирают pool, не делают новый TMDb-запрос и не удаляют кандидатов из candidate_pool.json.")
    print(f"KP: {updated.get('min_kp', 'не важно')}")
    print(f"Жанры (saved pool): {', '.join(updated.get('genres', [])) or 'не важно'}")
    print(f"Жанры исключить (saved pool): {', '.join(updated.get('excluded_genres', [])) or 'не важно'}")


def show_candidate_pool() -> None:
    """Показывает кандидатов общего pool в консоли."""
    ui.clean_terminal()
    candidates = candidate_service.get_pool_view()
    pool_stats_view = candidate_service.get_pool_stats_view()
    criteria_view = candidate_service.get_common_pool_criteria_view()
    criteria = criteria_view.get("criteria") or {}

    print("\nОбщий pool кандидатов")
    print(f"Страна: {criteria.get('country') or 'не важно'}")
    for line in pool_stats_view["lines"]:
        print(line)
    print("")

    if len(candidates) == 0:
        print("Общий pool пока пуст.")
        return

    for idx, candidate in enumerate(candidates, start=1):
        title = candidate.get("title") or "Без названия"
        year = candidate.get("year") or "?"
        kp_score = candidate.get("kp_score")
        imdb_score = candidate.get("imdb_score")
        kp_votes = candidate.get("kp_votes")
        genres = ", ".join(genre_schema.candidate_genres_for_display(candidate)) or "нет"
        description = request.short_text(candidate.get("description"), 80) or "без описания"
        kp_status = candidate.get("kp_status")
        is_complete = candidate.get("is_complete")

        kp_score_label = kp_score if kp_score is not None else "-"
        imdb_score_label = imdb_score if imdb_score is not None else "-"
        kp_votes_label = kp_votes if kp_votes is not None else "-"

        print(f"{idx}) {title} ({year})")
        print(f"   KP: {kp_score_label} | IMDb: {imdb_score_label} | KP votes: {kp_votes_label}")
        if kp_status is not None or is_complete is not None:
            complete_label = "yes" if is_complete is True else "no"
            print(f"   KP status: {kp_status or 'unknown'} | complete: {complete_label}")
        print(f"   Жанры: {genres}")
        print(f"   Описание: {description}\n")


def show_global_candidate_top() -> None:
    """Legacy wrapper for the candidate search console screen."""
    from ui.console import search_menu

    search_menu.show_global_candidate_search()


def _print_incomplete_candidates_preview(candidates: list, limit: int = 5) -> None:
    if len(candidates) == 0:
        return

    preview = candidates[:limit]
    for index, candidate in enumerate(preview, start=1):
        title = candidate.get("title") or "Без названия"
        year = candidate.get("year") or "?"
        kp_status = candidate.get("kp_status") or "unknown"
        complete_label = "yes" if candidate.get("is_complete") is True else "no"
        print(f"{index}. {title} ({year}) | KP status: {kp_status} | complete: {complete_label}")

    remaining = len(candidates) - len(preview)
    if remaining > 0:
        print(f"\n...и ещё {remaining}")


def retry_kp_for_incomplete_candidates() -> None:
    """Запускает повторный добор KP-данных для неполных кандидатов общего пула."""
    ui.clean_terminal()
    retry_view = candidate_service.get_retry_kp_view()
    if retry_view["is_empty"]:
        print("Общий пул кандидатов пуст.")
        return

    print("Добор KP для неполных кандидатов\n")
    print(f"Неполных кандидатов всего: {retry_view['incomplete_count']}")
    if retry_view["incomplete_count"] == 0:
        print("Добор не требуется.")
        return

    scoped_incomplete = retry_view["incomplete_candidates"]
    if len(scoped_incomplete) == 0:
        print("Для выбранного набора неполных кандидатов нет.")
        return

    limit_answer = input("Лимит попыток [10] >> ").strip()
    try:
        limit = int(limit_answer or 10)
    except ValueError:
        limit = 10
    limit = max(1, min(limit, len(scoped_incomplete)))
    selected_candidates = scoped_incomplete[:limit]

    print("\nБудет запущен добор KP:")
    print(f"Неполных найдено: {len(scoped_incomplete)}")
    print(f"Попыток будет выполнено: {limit}")
    print("\nПервые кандидаты на добор:\n")
    _print_incomplete_candidates_preview(selected_candidates, limit=limit)
    answer = input("\nЗапустить добор KP для этих кандидатов? [y/N] ").strip().casefold()
    if answer not in {"y", "yes", "д", "да"}:
        print("Добор KP отменён.")
        return

    result = candidate_service.retry_kp_enrichment_in_pool(limit=limit)
    stats = result["stats"]

    print("\nДобор KP завершён.")
    print(f"Неполных найдено: {stats['incomplete_found']}")
    print(f"Попыток выполнено: {stats['attempted']}")
    print(f"KP найден: {stats['kp_found']}")
    print(f"KP не найден: {stats['kp_not_found']}")
    print(f"Ошибок API: {stats['api_errors']}")
    print(f"Стали complete: {stats['became_complete']}")
    print(f"Остались incomplete: {stats['remaining_incomplete']}")


def delete_candidate_pool() -> None:
    """Очищает общий candidate pool."""
    ui.clean_terminal()
    pool_stats_view = candidate_service.get_pool_stats_view()
    stats = pool_stats_view["stats"]
    total = stats.get("unique_total", stats.get("storage_total", 0))
    if total == 0:
        print("Общий pool уже пуст.")
        return

    answer = input(f"\nОчистить общий pool ({total} уникальных кандидатов)? yes >> ").strip().lower()
    if answer != "yes":
        print("Очистка отменена.")
        return

    delete_result = candidate_service.clear_common_candidate_pool()
    print("Общий pool очищен.")
    print(f"Удалено кандидатов: {delete_result['cleared']}")


def clean_common_pool_duplicates() -> None:
    """Удаляет exact- и похожие дубли из общего pool после merge старых пуллов."""
    ui.clean_terminal()
    pool_stats_view = candidate_service.get_pool_stats_view()
    stats = pool_stats_view["stats"]
    unique_total = stats.get("unique_total", stats.get("storage_total", 0))
    duplicate_entries = int(stats.get("duplicate_entries") or 0)
    similar_duplicate_total = int(stats.get("similar_duplicate_total") or 0)
    cross_year_duplicate_total = int(stats.get("cross_year_duplicate_total") or 0)

    if unique_total == 0:
        print("Общий pool пуст.")
        return

    print("Очистка дублей в общем pool\n")
    for line in pool_stats_view["lines"]:
        print(line)
    print("")
    if duplicate_entries == 0 and similar_duplicate_total == 0 and cross_year_duplicate_total == 0:
        print("Exact-, похожие и cross-year дубли не найдены. JSON уже соответствует уникальным кандидатам.")
        return

    print("Будет выполнено:")
    if duplicate_entries > 0:
        print(f"- exact-дубли и legacy-ключи: до {duplicate_entries}")
    if similar_duplicate_total > 0:
        print(f"- похожие названия одного года: до {similar_duplicate_total}")
    if cross_year_duplicate_total > 0:
        print(f"- cross-year (±1 год, одно название): до {cross_year_duplicate_total}")
    print("Останется лучшая запись по рейтингу и полноте данных.")

    answer = input("\nОчистить дубли? [y/N] >> ").strip().casefold()
    if answer not in {"y", "yes", "д", "да"}:
        print("Очистка отменена.")
        return

    result = candidate_service.clean_common_pool_duplicates()
    print("\nОчистка завершена.")
    print(f"Было записей в JSON: {result['raw_total']}")
    print(f"Стало уникальных: {result['unique_total']}")
    print(f"Удалено exact-дублей: {result['removed_exact']}")
    print(f"Слито похожих: {result['removed_similar']}")
    print(f"Слито cross-year: {result.get('removed_cross_year', 0)}")
    print(f"Всего убрано: {result['removed_total']}")
    if result["changed"] is False:
        print("JSON не изменился.")


def purge_pool_dataset_title_matches() -> None:
    """Удаляет из pool записи, чьё normalized title уже есть в датасете."""
    ui.clean_terminal()
    preview = candidate_service.get_pool_dataset_title_matches_view()
    if preview["is_empty"]:
        print("В pool нет записей с названиями из датасета.")
        return

    print("Удаление из pool тайтлов, уже есть в датасете\n")
    print(f"Будет удалено записей: {preview['match_count']}\n")
    for idx, match in enumerate(preview["matches"], start=1):
        print(f"{idx}) {match.get('title')} ({match.get('year') or '?'})")

    answer = input("\nУдалить эти записи из pool? [y/N] >> ").strip().casefold()
    if answer not in {"y", "yes", "д", "да"}:
        print("Удаление отменено.")
        return

    result = candidate_service.purge_pool_dataset_title_matches()
    print("\nГотово.")
    print(f"Было записей: {result['raw_total']}")
    print(f"Стало: {result['unique_total']}")
    print(f"Удалено: {result['removed_dataset_title_matches']}")
    if result["changed"] is False:
        print("JSON не изменился.")


def show_suspicious_candidate_duplicates() -> None:
    """Показывает подозрительно похожие дубли в общем пуле."""
    ui.clean_terminal()
    duplicates_view = candidate_service.get_suspicious_duplicates_view()
    if duplicates_view["is_empty"]:
        print("Подозрительных дублей в общем пуле не найдено.")
        return

    print("Подозрительные дубли в общем пуле:\n")
    for idx, pair in enumerate(duplicates_view["pairs"], start=1):
        left = pair["left"]
        right = pair["right"]
        print(f"{idx}) Похожесть: {pair['ratio']:.2f}")
        print(
            f"   A: {left.get('title')} ({left.get('year')}) "
            f"| критерий: {left.get('criteria_name')}"
        )
        print(
            f"   B: {right.get('title')} ({right.get('year')}) "
            f"| критерий: {right.get('criteria_name')}"
        )
        print("")


def show_cross_year_candidate_duplicates() -> None:
    """Показывает группы cross-year дублей в общем пуле."""
    ui.clean_terminal()
    duplicates_view = candidate_service.get_cross_year_duplicates_view()
    if duplicates_view["is_empty"]:
        print("Cross-year дублей в общем пуле не найдено.")
        return

    print("Cross-year дубли (одно название, разный год):\n")
    for idx, group in enumerate(duplicates_view["groups"], start=1):
        years = group.get("years") or []
        years_text = ", ".join(str(year) for year in years) if years else "?"
        print(f"{idx}) {group.get('title')} | годы: {years_text}")
        for entry in group.get("entries") or []:
            year = entry.get("year") or "?"
            source = entry.get("source") or entry.get("criteria_name") or "?"
            kp_id = entry.get("kp_id") or entry.get("id") or "-"
            imdb_id = entry.get("imdb_id") or "-"
            tmdb_id = entry.get("tmdb_id") or "-"
            print(
                f"   - ({year}) source={source} | KP={kp_id} | IMDb={imdb_id} | TMDb={tmdb_id}"
            )
        print("")


def show_title_candidate_duplicates() -> None:
    """Показывает сводку и группы дублей с одним normalized title."""
    ui.clean_terminal()
    duplicates_view = candidate_service.get_title_duplicates_view()
    if duplicates_view["is_empty"]:
        print("Дублей по названию и совпадений с датасетом не найдено.")
        return

    group_count = int(duplicates_view.get("group_count") or 0)
    extra_entries = int(duplicates_view.get("extra_entries") or 0)
    reported_groups = int(duplicates_view.get("reported_groups") or duplicates_view.get("count") or 0)
    dataset_overlap_count = int(duplicates_view.get("dataset_overlap_count") or 0)
    print("Дубли по названию (pool + совпадения с датасетом):\n")
    print(f"Названий с повторами в pool: {group_count}")
    print(f"Лишних записей в pool: {extra_entries}")
    print(f"Совпадает с датасетом: {dataset_overlap_count}")
    print(f"Показано групп: {reported_groups}\n")

    for idx, group in enumerate(duplicates_view["groups"], start=1):
        entry_count = int(group.get("entry_count") or 0)
        dataset_count = int(group.get("dataset_count") or 0)
        years = group.get("years") or []
        years_text = ", ".join(str(year) for year in years) if years else "?"
        markers = []
        if entry_count >= 2:
            markers.append(f"pool x{entry_count}")
        if dataset_count > 0:
            markers.append(f"dataset x{dataset_count}")
        marker_text = " | ".join(markers) if markers else "?"
        print(f"{idx}) {group.get('title')} | {marker_text} | годы: {years_text}")
        for entry in group.get("entries") or []:
            year = entry.get("year") or "?"
            source = entry.get("source") or entry.get("criteria_name") or "?"
            kp_id = entry.get("kp_id") or entry.get("id") or "-"
            imdb_id = entry.get("imdb_id") or "-"
            tmdb_id = entry.get("tmdb_id") or "-"
            print(
                f"   [pool] ({year}) source={source} | KP={kp_id} | IMDb={imdb_id} | TMDb={tmdb_id}"
            )
        for dataset_entry in group.get("dataset_entries") or []:
            year = dataset_entry.get("year") or "?"
            dataset_key = dataset_entry.get("dataset_key") or "?"
            title = dataset_entry.get("title") or dataset_key
            print(f"   [dataset] {title} ({year}) | key={dataset_key}")
        print("")


def show_candidate_poster_diagnostics() -> None:
    """Показывает покрытие постерами в общем candidate pool."""
    ui.clean_terminal()
    view = candidate_service.get_candidate_poster_diagnostics_view()
    if view.get("is_empty_pool"):
        print("Общий candidate pool пуст.")
        return

    total = int(view.get("total") or 0)
    counts = view.get("counts") or {}
    displayable = int(counts.get("displayable") or 0)
    metadata_only = int(counts.get("metadata_only") or 0)
    missing = int(counts.get("missing") or 0)

    def pct(value: int) -> str:
        if total <= 0:
            return "0%"
        return f"{(100 * value / total):.1f}%"

    print("Диагностика постеров в общем candidate pool\n")
    print(f"Всего кандидатов: {total}")
    print(f"  Отображаются в GUI (локальный файл): {displayable} ({pct(displayable)})")
    print(f"  Есть metadata, но нет локального файла: {metadata_only} ({pct(metadata_only)})")
    print(f"  Без poster metadata: {missing} ({pct(missing)})")
    print("")
    print("Источники poster metadata:")
    source_counts = view.get("source_counts") or {}
    for source, count in sorted(source_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {source}: {count}")
    print("")
    print("Примеры без отображаемого постера (до 30):")
    problem_rows = list(view.get("problem_rows") or [])[:30]
    if len(problem_rows) == 0:
        print("  Все кандидаты имеют локальный постер.")
        return

    state_labels = {
        "metadata_only": "metadata без файла",
        "missing": "нет metadata",
    }
    for idx, row in enumerate(problem_rows, start=1):
        candidate = row.get("candidate") or {}
        title = candidate.get("title") or candidate.get("name") or "Без названия"
        year = candidate.get("year") or "?"
        criteria_name = candidate.get("criteria_name") or "—"
        state = row.get("display_state") or "missing"
        source = row.get("source") or "—"
        poster_url = row.get("poster_url")
        poster_path = row.get("poster_path")
        poster_hint = request.short_text(poster_url or poster_path, 70) if (poster_url or poster_path) else "—"
        print(
            f"{idx}) {title} ({year}) | {state_labels.get(state, state)} "
            f"| критерий: {criteria_name} | source: {source}"
        )
        print(f"   poster: {poster_hint}")


def download_candidate_pool_preview_posters() -> None:
    """Download unique candidate pool poster URLs into preview cache for desktop GUI."""
    ui.clean_terminal()
    print("Скачивание постеров candidate pool в preview-cache...")
    print(
        f"(TMDb URL -> {PREVIEW_DOWNLOAD_SIZE}, пауза {PREVIEW_BULK_DELAY_SECONDS:g}s, "
        f"batch {PREVIEW_BATCH_SIZE}, retry на 403/SSL)\n"
    )

    def progress(current: int, total: int, url: str) -> None:
        label = request.short_text(url, 70) if url else "—"
        print(f"  [{current}/{total}] {label}")

    def on_error(url: str, reason: str) -> None:
        label = request.short_text(url, 70) if url else "—"
        print(f"      ! {reason} | {label}")

    result = candidate_service.download_candidate_pool_preview_posters(
        progress_callback=progress,
        error_callback=on_error,
    )
    if result.get("is_empty_pool"):
        print("\nОбщий candidate pool пуст.")
        return

    print("")
    print(f"  Записей в pool: {result.get('pool_total', 0)}")
    print(f"  Уникальных poster URL: {result.get('unique_urls', 0)}")
    print(f"  Скачано: {result.get('downloaded', 0)}")
    print(f"  Уже были в cache: {result.get('skipped_existing', 0)}")
    print(f"  Ошибок: {result.get('failed', 0)}")
    skipped_invalid = int(result.get("skipped_invalid") or 0)
    if skipped_invalid > 0:
        print(f"  Пропущено (невалидный URL): {skipped_invalid}")

    failures = list(result.get("failures") or [])
    if len(failures) > 0 and int(result.get("failed") or 0) > len(failures):
        print("  (часть ошибок уже показана выше построчно)")
