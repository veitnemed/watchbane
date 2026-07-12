"""Console workflows for candidate pool maintenance and diagnostics."""

from candidates import service as candidate_service
from candidates.models import genre_schema
from posters.download_images import PREVIEW_BATCH_SIZE, PREVIEW_BULK_DELAY_SECONDS, PREVIEW_DOWNLOAD_SIZE
from ui.console import candidate_pool_ui
from ui.console import request
from ui.console import ui


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
    print(f"Текущий TMDb: {criteria.get('min_tmdb_score', criteria.get('min_tmdb', 'не важно'))}")
    print(f"Текущие жанры (saved pool): {', '.join(criteria.get('genres', [])) or 'не важно'}")
    print(f"Исключить жанры (saved pool): {', '.join(criteria.get('excluded_genres', [])) or 'не важно'}\n")

    updated = candidate_pool_ui.update_criteria_filters(criteria_name, criteria)
    print("\nDefaults обновлены в SQLite candidate criteria.")
    print("Filters сохраняются как defaults поиска по уже сохранённым кандидатам (Enter = default).")
    print("Ручной ввод в поиске действует только на текущий запуск.")
    print("Filters не пересобирают pool, не делают новый TMDb-запрос и не удаляют кандидатов из SQLite candidate pool.")
    print(f"TMDb: {updated.get('min_tmdb_score', updated.get('min_tmdb', 'не важно'))}")
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
        tmdb_score = candidate.get("tmdb_score")
        tmdb_votes = candidate.get("tmdb_votes")
        final_score = candidate.get("final_score")
        genres = ", ".join(genre_schema.candidate_genres_for_display(candidate)) or "нет"
        description = request.short_text(candidate.get("description"), 80) or "без описания"
        is_complete = candidate.get("is_complete")
        missing_fields = candidate.get("missing_fields") or []

        tmdb_score_label = tmdb_score if tmdb_score is not None else "-"
        tmdb_votes_label = tmdb_votes if tmdb_votes is not None else "-"
        final_score_label = final_score if final_score is not None else "-"

        print(f"{idx}) {title} ({year})")
        print(f"   TMDb: {tmdb_score_label} | votes: {tmdb_votes_label} | итог: {final_score_label}")
        if is_complete is not None or missing_fields:
            complete_label = "yes" if is_complete is True else "no"
            missing_label = ", ".join(str(item) for item in missing_fields) or "-"
            print(f"   metadata complete: {complete_label} | missing: {missing_label}")
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
        complete_label = "yes" if candidate.get("is_complete") is True else "no"
        missing = ", ".join(str(item) for item in (candidate.get("missing_fields") or [])) or "-"
        print(f"{index}. {title} ({year}) | metadata complete: {complete_label} | missing: {missing}")

    remaining = len(candidates) - len(preview)
    if remaining > 0:
        print(f"\n...и ещё {remaining}")


def show_candidate_metadata_diagnostics() -> None:
    """Shows read-only diagnostics for candidates missing TMDb/core metadata."""
    ui.clean_terminal()
    diagnostics_view = candidate_service.get_metadata_diagnostics_view()
    if diagnostics_view["is_empty"]:
        print("Общий пул кандидатов пуст.")
        return

    print("Диагностика metadata кандидатов\n")
    print("Incomplete = не хватает TMDb/core metadata для candidate contract.")
    print(f"Неполных кандидатов всего: {diagnostics_view['incomplete_count']}")
    if diagnostics_view["incomplete_count"] == 0:
        print("Проблем metadata не найдено.")
        return

    scoped_incomplete = diagnostics_view["incomplete_candidates"]
    if len(scoped_incomplete) == 0:
        print("Для выбранного набора неполных кандидатов нет.")
        return

    _print_incomplete_candidates_preview(scoped_incomplete, limit=20)


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
            imdb_id = entry.get("imdb_id") or "-"
            tmdb_id = entry.get("tmdb_id") or "-"
            print(
                f"   - ({year}) source={source} | TMDb={tmdb_id} | IMDb ID={imdb_id}"
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
            imdb_id = entry.get("imdb_id") or "-"
            tmdb_id = entry.get("tmdb_id") or "-"
            print(
                f"   [pool] ({year}) source={source} | TMDb={tmdb_id} | IMDb ID={imdb_id}"
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

    diagnostics = candidate_service.get_candidate_poster_diagnostics_view()
    if diagnostics.get("is_empty_pool"):
        print("\nОбщий candidate pool пуст.")
        return

    counts = diagnostics.get("counts") or {}
    total = int(diagnostics.get("total") or 0)
    displayable = int(counts.get("displayable") or 0)
    metadata_only = int(counts.get("metadata_only") or 0)
    missing = int(counts.get("missing") or 0)

    print(f"  Pool records: {total}")
    print(f"  Local preview posters: {displayable}")
    print(f"  Need download: {metadata_only}")
    print(f"  Without poster metadata: {missing}\n")

    if metadata_only == 0:
        print("Nothing to download: all available poster URLs already have local previews.")
        return

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
    print(f"  Already displayable: {result.get('already_displayable', 0)}")
    print(f"  Download queue: {result.get('download_queue_total', result.get('unique_urls', 0))}")
    print(f"  Without poster metadata: {result.get('poster_missing', 0)}")
    print(f"  Скачано: {result.get('downloaded', 0)}")
    print(f"  Уже были в cache: {result.get('skipped_existing', 0)}")
    print(f"  Ошибок: {result.get('failed', 0)}")
    skipped_invalid = int(result.get("skipped_invalid") or 0)
    if skipped_invalid > 0:
        print(f"  Пропущено (невалидный URL): {skipped_invalid}")

    failures = list(result.get("failures") or [])
    if len(failures) > 0 and int(result.get("failed") or 0) > len(failures):
        print("  (часть ошибок уже показана выше построчно)")


def _print_candidate_poster_job_status(status: dict) -> None:
    status_labels = {
        "idle": "не запускалась",
        "starting": "запускается",
        "running": "идёт загрузка",
        "stopping": "останавливается",
        "stopped": "остановлена",
        "finished": "завершена",
        "failed": "ошибка",
        "stale_lock": "зависший lock",
    }
    raw_status = status.get("status") or "idle"
    print(f"Задача: {status.get('job_name') or 'candidates'}")
    print(f"Статус: {status_labels.get(raw_status, raw_status)}")
    print(f"Запущена: {'да' if status.get('is_running') else 'нет'}")
    print(f"Прогресс: {status.get('processed_urls', 0)}/{status.get('total_urls', 0)}")
    print(
        f"Скачано: {status.get('downloaded', 0)} | "
        f"уже было в cache: {status.get('skipped_existing', 0)} | "
        f"ошибок: {status.get('failed', 0)} | "
        f"невалидных URL: {status.get('skipped_invalid', 0)}"
    )
    queue_total = status.get("download_queue_total")
    if queue_total is not None:
        print(f"Очередь скачивания: {queue_total}")
    if status.get("stop_requested"):
        print("Остановка запрошена: да")
    if status.get("last_url"):
        print(f"Последний URL: {request.short_text(status.get('last_url'), 90)}")
    if status.get("is_empty_pool") is True:
        print("Candidate pool пуст или нет URL для скачивания.")
    if status.get("error"):
        print(f"Ошибка: {status.get('error')}")


def start_candidate_pool_preview_poster_job() -> None:
    """Start background preview-poster download for candidate pool."""
    from posters import download_job

    ui.clean_terminal()
    print("Фоновая загрузка preview-постеров candidate pool\n")
    result = download_job.start_job("candidates")
    if result.get("ok"):
        print("Загрузка запущена в фоне.")
        print(f"PID: {result.get('pid')}")
        print("Статус можно смотреть в этом же меню.")
        return

    if result.get("already_running"):
        print("Фоновая загрузка уже запущена.")
    else:
        print(f"Не удалось запустить загрузку: {result.get('message') or result.get('error')}")

    _print_candidate_poster_job_status(download_job.get_status("candidates"))


def show_candidate_pool_preview_poster_job_status() -> None:
    """Show background candidate preview-poster download status."""
    from posters import download_job

    ui.clean_terminal()
    print("Статус фоновой загрузки preview-постеров\n")
    _print_candidate_poster_job_status(download_job.get_status("candidates"))


def show_candidate_pool_preview_poster_job_log(lines: int = 40) -> None:
    """Show recent background candidate preview-poster download log lines."""
    from posters import download_job

    ui.clean_terminal()
    print(f"Лог фоновой загрузки preview-постеров, последние {lines} строк\n")
    log_tail = download_job.get_log_tail("candidates", lines=lines)
    if log_tail.strip() == "":
        print("Лог пока пуст.")
        return
    print(log_tail)


def stop_candidate_pool_preview_poster_job() -> None:
    """Request graceful stop for background candidate preview-poster download."""
    from posters import download_job

    ui.clean_terminal()
    print("Остановка фоновой загрузки preview-постеров\n")
    result = download_job.stop_job("candidates")
    print(result.get("message") or "Запрос на остановку записан.")
    print("")
    _print_candidate_poster_job_status(download_job.get_status("candidates"))
