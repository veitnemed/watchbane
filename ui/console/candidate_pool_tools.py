"""Console workflows for candidate pool maintenance and diagnostics."""

from candidates import service as candidate_service
from candidates.models import genre_schema
from posters.download_images import PREVIEW_BATCH_SIZE, PREVIEW_BULK_DELAY_SECONDS, PREVIEW_DOWNLOAD_SIZE
from ui.console import candidate_pool_ui
from ui.console import request
from ui.console import ui


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

    diagnostics = candidate_service.get_candidate_poster_diagnostics_view()
    if diagnostics.get("is_empty_pool"):
        print("\nРћР±С‰РёР№ candidate pool РїСѓСЃС‚.")
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
