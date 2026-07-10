"""Содержит действия интерфейса, которые запускаются из пунктов меню."""

from candidates import service as candidate_service
from dataset import service
from ui.console.api_tools import ping_external_apis
from ui.console.candidate_pool_tools import (
    clean_common_pool_duplicates,
    delete_candidate_pool,
    download_candidate_pool_preview_posters,
    edit_candidate_pool_filters,
    purge_pool_dataset_title_matches,
    show_candidate_pool,
    show_candidate_metadata_diagnostics,
    show_candidate_poster_diagnostics,
    show_cross_year_candidate_duplicates,
    show_global_candidate_top,
    show_suspicious_candidate_duplicates,
    show_title_candidate_duplicates,
)
from ui.console import request
from ui.console import title_presenters
from ui.console.poster_tools import (
    diagnose_unresolved_watched_tmdb_metadata,
    download_poster_images_local,
    fetch_tmdb_poster_metadata,
    fetch_watched_tmdb_metadata,
    sync_watched_descriptions_and_posters,
)
from ui.console.tmdb_pool_tools import (
    ask_auto_import_choice,
    import_tmdb_result_to_common_pool_flow,
    maybe_auto_import_tmdb_result,
    request_tmdb_country_codes,
    request_tmdb_discover_genre_filters,
    run_tmdb_candidate_pool_flow,
    show_tmdb_dataset_genre_diagnostics,
)
from storage import data as storage_data
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

    movie_request = request.request_user_score(defaults)
    result = service.add_movie(
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
    transfer_payload = service.build_candidate_transfer_payload(candidate)
    defaults = transfer_payload["defaults"]
    meta_payload = transfer_payload["meta_payload"]
    if candidate_service.is_pool_candidate_incomplete(candidate):
        print("Кандидат неполный: не хватает TMDb/core metadata.")
        print("Можно продолжить вручную, но проверь карточку перед добавлением.\n")
    print_candidate_genre_transfer_preview(
        service.build_candidate_genre_transfer_preview(candidate)
    )
    movie_request = request.request_user_score(defaults)
    result = service.add_movie(
        movie_request,
        meta_payload=meta_payload,
        pool_candidate=candidate,
        print_message=False,
    )
    print(result.message)


def show_data_info():
    """Показывает сводку по датасету."""
    data = storage_data.load_dataset()
    for line in service.build_dataset_info_lines(data):
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

    matches = service.search_watched_records_by_query(query, data=data)
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

    preview = service.build_watched_delete_preview(selected["dataset_key"], data=data)
    if preview is None:
        print("Запись не найдена.")
        return

    print()
    print(service.format_watched_delete_preview(preview))
    print()
    confirmation = input("Введите DELETE для удаления: ").strip()
    if confirmation != "DELETE":
        print("Удаление отменено.")
        return

    result = service.delete_watched_record(selected["dataset_key"])
    print()
    print(service.format_watched_delete_report(result))
    if result.get("ok") is False:
        print("Данные не изменены.")


def show_dataset_genres() -> None:
    """Показывает все жанры текущего датасета через API."""
    ui.clean_terminal()
    service.show_dataset_genres()

    """Ищет сериал через TMDb и печатает краткую сводку найденного объекта."""
    title = request.loop_input(
        text='Название сериала >> ',
        funcs_list=[valid.is_correct_title]
    )
    result = service.resolve_title_data_for_add(title, "Россия")

    if result["found"] is False:
        error = result.get("tmdb_error") or {}
        print(f'Сериал не найден в TMDb: {error.get("details") or error.get("error") or "нет данных"}')
        return

    print('\nСериал найден в TMDb.\n')
    title_presenters.print_api_add_preview(result["tmdb_data"])


def show_dataset_genres() -> None:
    """Показывает все жанры текущего датасета через API."""
    ui.clean_terminal()
    service.show_dataset_genres()




































