"""Собирает и хранит пул кандидатов по сохраненным критериям."""

import json
import os
import time
from datetime import datetime
from difflib import SequenceMatcher

from config import constant
from config import genre_tags
from common import format_score
from apis import kp_api as api
from candidates.keys import normalize_key_part, pool_entry_key, title_identity_key
from candidates import country_schema
from candidates import genre_schema
from candidates import genres as candidate_genres
from candidates.schema import (
    compute_completeness as schema_compute_completeness,
    is_ready_for_predict as schema_is_ready_for_predict,
    normalize_candidate_record,
)

DISCOVER_PAGE_LIMIT = 30
DISCOVER_PAGE_PAUSE_SECONDS = 1.0


def init_candidate_criteria() -> None:
    """Создает JSON с критериями подбора, если его еще нет."""
    if os.path.exists(constant.CRITERIA_POOL_JSON):
        return
    os.makedirs(constant.DATA_DIR, exist_ok=True)
    with open(constant.CRITERIA_POOL_JSON, "w", encoding="utf-8") as file:
        json.dump({}, file, ensure_ascii=False, indent=4)


def init_candidate_pool() -> None:
    """Создает JSON с пулом кандидатов, если его еще нет."""
    if os.path.exists(constant.CANDIDATE_POOL_JSON):
        return
    os.makedirs(constant.DATA_DIR, exist_ok=True)
    with open(constant.CANDIDATE_POOL_JSON, "w", encoding="utf-8") as file:
        json.dump({}, file, ensure_ascii=False, indent=4)


def load_candidate_criteria() -> dict:
    """Загружает сохраненные критерии подбора."""
    init_candidate_criteria()
    with open(constant.CRITERIA_POOL_JSON, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def save_candidate_criteria(data: dict) -> None:
    """Сохраняет критерии подбора."""
    with open(constant.CRITERIA_POOL_JSON, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def load_candidate_pool() -> dict:
    """Загружает текущий пул кандидатов."""
    init_candidate_pool()
    with open(constant.CANDIDATE_POOL_JSON, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def save_candidate_pool(data: dict) -> None:
    """Сохраняет пул кандидатов."""
    data = purge_watched_from_pool(normalize_storage_pool(data))
    with open(constant.CANDIDATE_POOL_JSON, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def save_named_criteria(criteria_name: str, criteria: dict) -> tuple[str, dict]:
    """Сохраняет именованный набор критериев и возвращает его."""
    all_criteria = load_candidate_criteria()
    all_criteria[criteria_name] = criteria
    save_candidate_criteria(all_criteria)
    return criteria_name, criteria


def patch_criteria_filters(
    criteria_name: str,
    current: dict,
    *,
    min_kp,
    genres: list,
    excluded_genres: list,
) -> dict:
    """Обновляет у набора критериев только блок фильтрации."""
    all_criteria = load_candidate_criteria()

    updated = dict(current)
    updated["min_kp"] = min_kp
    updated["genres"] = genres
    updated["excluded_genres"] = excluded_genres
    updated["updated_at"] = datetime.now().isoformat(timespec="seconds")

    all_criteria[criteria_name] = updated
    save_candidate_criteria(all_criteria)
    return updated


def normalize_genre_list(raw_value: str) -> list:
    """Нормализует строку жанров через запятую."""
    genres = []
    for item in str(raw_value or "").split(","):
        genre = item.strip()
        if genre != "":
            genres.append(genre)
    return genres


def get_available_genres() -> list:
    """Возвращает список доступных жанров для выбора в критериях."""
    tags = genre_tags.load_genre_tags()
    genres = []
    for settings in tags.values():
        source = str(settings.get("source", "")).strip()
        if source != "":
            genres.append(source)
    return sorted(set(genres))


def build_criteria_label(criteria_name: str, criteria: dict) -> str:
    """Формирует короткую подпись сохраненного набора критериев."""
    parts = [criteria_name]
    if criteria.get("count"):
        parts.append(f"count={criteria['count']}")
    if criteria.get("min_kp") is not None:
        parts.append(f"KP>={criteria['min_kp']}")
    if criteria.get("min_year") is not None:
        parts.append(f"year>={criteria['min_year']}")
    if criteria.get("country"):
        parts.append(criteria["country"])
    if criteria.get("genres"):
        parts.append(f"жанры={len(criteria['genres'])}")
    if criteria.get("excluded_genres"):
        parts.append(f"искл={len(criteria['excluded_genres'])}")
    return " | ".join(parts)


def delete_criteria_and_candidates(criteria_name: str) -> dict:
    """Удаляет набор критериев и все связанные с ним объекты из общего пула."""
    all_criteria = load_candidate_criteria()
    if criteria_name not in all_criteria:
        return {
            "deleted_criteria": False,
            "deleted_candidates": 0,
        }

    all_criteria.pop(criteria_name, None)
    save_candidate_criteria(all_criteria)

    pool = normalize_storage_pool(load_candidate_pool())
    filtered_pool = {}
    deleted_candidates = 0
    for key, candidate in pool.items():
        if candidate.get("criteria_name") == criteria_name:
            deleted_candidates += 1
            continue
        filtered_pool[key] = candidate
    save_candidate_pool(filtered_pool)

    return {
        "deleted_criteria": True,
        "deleted_candidates": deleted_candidates,
    }


def candidate_key(movie: dict) -> str:
    """Строит стабильный ключ кандидата для дедупликации."""
    return title_identity_key(movie)


def normalized_title_key(title: str) -> str:
    """Нормализует название для дедупликации кандидатов."""
    title = str(title or "").strip().casefold()
    title = title.replace("ё", "е")
    for char in [".", ",", "!", "?", ":", ";", "\"", "'", "`", "«", "»", "(", ")", "[", "]"]:
        title = title.replace(char, " ")
    while "  " in title:
        title = title.replace("  ", " ")
    return title.strip()


def compact_title_key(title: str) -> str:
    """Возвращает компактное название без пробелов для мягкого сравнения."""
    return normalized_title_key(title).replace(" ", "")


def titles_are_similar(left_title: str, right_title: str) -> bool:
    """Проверяет, что два названия достаточно похожи для дедупликации."""
    left = normalized_title_key(left_title)
    right = normalized_title_key(right_title)
    if left == "" or right == "":
        return False
    if left == right:
        return True

    left_compact = compact_title_key(left)
    right_compact = compact_title_key(right)
    if left_compact == right_compact:
        return True

    ratio = SequenceMatcher(None, left_compact, right_compact).ratio()
    if ratio >= 0.92:
        return True

    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if left_tokens and right_tokens and left_tokens == right_tokens:
        return True

    return False


def candidate_sort_score(candidate: dict) -> tuple:
    """Возвращает ключ качества кандидата для выбора лучшего дубля."""
    return (
        candidate.get("kp_score") or 0,
        candidate.get("kp_votes") or 0,
        candidate.get("imdb_score") or 0,
        candidate.get("imdb_votes") or 0,
    )


def candidate_pool_key(candidate: dict) -> str:
    """Строит ключ дедупликации для уже сохраненного кандидата."""
    return pool_entry_key(candidate)


def candidate_title(candidate: dict) -> str:
    """Возвращает лучшее доступное название кандидата."""
    return candidate.get("title") or candidate.get("alternative_title") or ""


def candidates_are_same(candidate: dict, other_candidate: dict, include_criteria: bool = True) -> bool:
    """Проверяет, относятся ли два кандидата к одному сериалу."""
    if include_criteria and (candidate.get("criteria_name") or "") != (other_candidate.get("criteria_name") or ""):
        return False

    left_year = candidate.get("year") or ""
    right_year = other_candidate.get("year") or ""
    if left_year != right_year:
        return False

    return titles_are_similar(candidate_title(candidate), candidate_title(other_candidate))


def deduplicate_pool(pool: dict) -> dict:
    """Удаляет дубли из пула, оставляя лучший вариант по рейтингу и голосам."""
    deduplicated = {}
    for candidate in pool.values():
        if isinstance(candidate, dict) is False:
            continue
        candidate = normalize_candidate_record(candidate)
        key = pool_entry_key(candidate)
        current_best = deduplicated.get(key)
        if current_best is None or candidate_sort_score(candidate) > candidate_sort_score(current_best):
            deduplicated[key] = candidate
    return deduplicated


def migrate_pool_keys(pool: dict) -> dict:
    """Переводит legacy-ключи пула на criteria-aware формат."""
    migrated = {}
    for candidate in pool.values():
        if isinstance(candidate, dict) is False:
            continue
        candidate = normalize_candidate_record(candidate)
        key = pool_entry_key(candidate)
        current_best = migrated.get(key)
        if current_best is None or candidate_sort_score(candidate) > candidate_sort_score(current_best):
            migrated[key] = candidate
    return migrated


def normalize_storage_pool(pool: dict) -> dict:
    """Приводит пул к каноническому виду без удаления просмотренных (read-path)."""
    if isinstance(pool, dict) is False:
        return {}
    return deduplicate_pool(migrate_pool_keys(pool))


def purge_watched_from_pool(pool: dict) -> dict:
    """Удаляет просмотренных кандидатов из пула (write-path only)."""
    return remove_watched_candidates(pool)


def normalize_pool(pool: dict) -> dict:
    """Legacy wrapper: только storage-normalize, без purge watched."""
    return normalize_storage_pool(pool)


def normalize_or_migrate_candidate_pool_file() -> dict:
    """Явно мигрирует и нормализует candidate_pool.json."""
    original = load_candidate_pool()
    normalized = purge_watched_from_pool(normalize_storage_pool(original))
    changed = normalized != original
    if changed:
        save_candidate_pool(normalized)
    return {
        "changed": changed,
        "before": len(original) if isinstance(original, dict) else 0,
        "after": len(normalized),
    }


def build_watched_signatures() -> set:
    """Собирает сигнатуры уже просмотренных объектов из основного датасета."""
    from storage import data as storage_data

    dataset = storage_data.load_dataset()
    signatures = set()
    for movie in dataset.values():
        main_info = movie.get("main_info", {})
        signature = title_identity_key({
            "title": main_info.get("title"),
            "year": main_info.get("year"),
        })
        if signature != "|":
            signatures.add(signature)
    return signatures


def is_watched_candidate(candidate: dict, watched_signatures: set | None = None) -> bool:
    """Проверяет, есть ли кандидат уже в основном датасете."""
    if watched_signatures is None:
        watched_signatures = build_watched_signatures()

    title = normalized_title_key(candidate.get("title") or candidate.get("alternative_title") or "")
    year = candidate.get("year") or ""
    exact_signature = title_identity_key(candidate)
    if exact_signature in watched_signatures:
        return True

    candidate_compact = compact_title_key(title)
    for watched_signature in watched_signatures:
        watched_title, _, watched_year = watched_signature.partition("|")
        if str(watched_year) != str(year):
            continue
        if titles_are_similar(candidate_compact, watched_title):
            return True
    return False


def remove_watched_candidates(pool: dict) -> dict:
    """Удаляет из пула кандидатов уже просмотренные объекты."""
    watched_signatures = build_watched_signatures()
    filtered = {}
    for key, candidate in pool.items():
        if is_watched_candidate(candidate, watched_signatures):
            continue
        filtered[key] = candidate
    return filtered


def movie_matches_genres(movie: dict, expected_genres: list, excluded_genres: list | None = None) -> bool:
    """Проверяет обязательные и исключенные жанры кандидата."""
    if excluded_genres is None:
        excluded_genres = []
    actual = {
        str(item.get("name", "")).strip().casefold()
        for item in movie.get("genres", []) or []
        if isinstance(item, dict) and item.get("name")
    }
    blocked = {genre.casefold() for genre in excluded_genres}
    if len(actual & blocked) > 0:
        return False
    if len(expected_genres) == 0:
        return True
    wanted = {genre.casefold() for genre in expected_genres}
    return len(actual & wanted) > 0


def normalize_candidate(movie: dict, criteria_name: str) -> dict:
    """Оставляет в пуле кандидатов полезные поля."""
    return normalize_candidate_record({
        "id": movie.get("id"),
        "title": movie.get("name") or movie.get("alternativeName") or movie.get("enName"),
        "alternative_title": movie.get("alternativeName") or movie.get("enName"),
        "year": movie.get("year"),
        "type": movie.get("type"),
        "description": movie.get("shortDescription") or movie.get("description"),
        "kp_score": api.safe_nested(movie, "rating", "kp"),
        "kp_votes": api.safe_nested(movie, "votes", "kp"),
        "imdb_score": api.safe_nested(movie, "rating", "imdb"),
        "imdb_votes": api.safe_nested(movie, "votes", "imdb"),
        "countries": [item.get("name") for item in movie.get("countries", []) or [] if isinstance(item, dict) and item.get("name")],
        "genres": [item.get("name") for item in movie.get("genres", []) or [] if isinstance(item, dict) and item.get("name")],
        "criteria_name": criteria_name,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    })


def collect_candidates(criteria_name: str, criteria: dict) -> dict:
    """Собирает новых кандидатов из API по критериям."""
    pool = normalize_storage_pool(load_candidate_pool())
    watched_signatures = build_watched_signatures()
    target_count = int(criteria.get("count") or 20)
    availability = api.check_api_available()
    if availability["ok"] is False:
        return {
            "criteria_name": criteria_name,
            "target_count": target_count,
            "added": 0,
            "duplicates": 0,
            "watched_skipped": 0,
            "scanned": 0,
            "last_page": 0,
            "pool_size": len(pool),
            "errors": [availability["details"]],
            "reached_end": False,
            "api_unavailable": True,
        }

    page = 1
    scanned = 0
    added = 0
    duplicates = 0
    watched_skipped = 0
    errors = []
    reached_end = False

    while added < target_count and page <= 20:
        result = api.discover_series_by_filters(criteria, page=page, limit=DISCOVER_PAGE_LIMIT)
        if result["ok"] is False:
            errors.append(result["details"] or result["error"] or "unknown_error")
            break

        docs = result["data"]
        if len(docs) == 0:
            reached_end = True
            break

        for movie in docs:
            scanned += 1

            if movie_matches_genres(
                movie,
                criteria.get("genres", []),
                criteria.get("excluded_genres", []),
            ) is False:
                continue

            candidate = normalize_candidate(movie, criteria_name)
            if is_watched_candidate(candidate, watched_signatures):
                watched_skipped += 1
                continue

            key = pool_entry_key(candidate)
            if key in pool:
                duplicates += 1
                continue

            pool[key] = candidate
            added += 1

            if added >= target_count:
                break

        page += 1
        if added < target_count:
            time.sleep(DISCOVER_PAGE_PAUSE_SECONDS)

    save_candidate_pool(pool)
    return {
        "criteria_name": criteria_name,
        "target_count": target_count,
        "added": added,
        "duplicates": duplicates,
        "watched_skipped": watched_skipped,
        "scanned": scanned,
        "last_page": page,
        "pool_size": len(pool),
        "errors": errors,
        "reached_end": reached_end,
        "api_unavailable": False,
    }


def get_candidates_by_criteria(criteria_name: str) -> list:
    """Возвращает кандидатов, собранных по выбранному набору критериев."""
    pool = normalize_storage_pool(load_candidate_pool())
    candidates = [
        candidate
        for candidate in pool.values()
        if candidate.get("criteria_name") == criteria_name
    ]
    candidates.sort(
        key=lambda item: (
            -(item.get("kp_score") or 0),
            -(item.get("kp_votes") or 0),
            str(item.get("title") or "")
        )
    )
    return candidates


def get_all_candidates() -> list:
    """Возвращает всех кандидатов из общего пула."""
    pool = normalize_storage_pool(load_candidate_pool())
    candidates = list(pool.values())
    candidates.sort(
        key=lambda item: (
            -(item.get("kp_score") or 0),
            -(item.get("kp_votes") or 0),
            str(item.get("title") or "")
        )
    )
    return candidates


def _count_raw_pool_entries(raw_pool: dict, criteria_name: str | None = None) -> int:
    if isinstance(raw_pool, dict) is False:
        return 0
    if criteria_name is None:
        return len(raw_pool)
    return sum(
        1
        for candidate in raw_pool.values()
        if isinstance(candidate, dict) and candidate.get("criteria_name") == criteria_name
    )


def get_pool_stats(criteria_name: str | None = None) -> dict:
    """Возвращает согласованные счётчики pool для UI и диагностики."""
    raw_pool = load_candidate_pool()
    storage_pool = normalize_storage_pool(raw_pool)
    watched_signatures = build_watched_signatures()

    candidates = [
        candidate
        for candidate in storage_pool.values()
        if isinstance(candidate, dict)
        and (criteria_name is None or candidate.get("criteria_name") == criteria_name)
    ]

    storage_total = len(candidates)
    watched_total = sum(
        1 for candidate in candidates
        if is_watched_candidate(candidate, watched_signatures)
    )
    ready_total = sum(
        1 for candidate in candidates
        if schema_is_ready_for_predict(candidate)
    )
    incomplete_total = storage_total - ready_total

    return {
        "criteria_name": criteria_name,
        "raw_total": _count_raw_pool_entries(raw_pool, criteria_name=criteria_name),
        "storage_total": storage_total,
        "watched_total": watched_total,
        "active_total": storage_total - watched_total,
        "ready_total": ready_total,
        "incomplete_total": incomplete_total,
    }


def format_pool_stats_summary(stats: dict) -> str:
    """Формирует однострочную сводку pool stats для меню."""
    parts = [
        f"в pool: {stats['storage_total']}",
        f"ready: {stats['ready_total']}",
        f"incomplete: {stats['incomplete_total']}",
    ]
    if stats.get("watched_total", 0) > 0:
        parts.append(f"watched: {stats['watched_total']}")
    if stats.get("criteria_name") is None and stats.get("raw_total") != stats.get("storage_total"):
        parts.append(f"JSON keys: {stats['raw_total']}")
    return " | ".join(parts)


def format_pool_stats_lines(stats: dict) -> list[str]:
    """Формирует многострочную сводку pool stats для экранов pool/top."""
    lines = [
        f"В pool (normalized): {stats['storage_total']}",
        f"Ready: {stats['ready_total']} | Incomplete: {stats['incomplete_total']}",
    ]
    if stats.get("watched_total", 0) > 0:
        lines.append(
            f"Watched in pool: {stats['watched_total']} "
            f"(после save active: {stats['active_total']})"
        )
    if stats.get("criteria_name") is None:
        lines.append(f"Записей в JSON: {stats['raw_total']}")
    return lines


def _format_optional_filter_value(value) -> str:
    if value in (None, ""):
        return "не важно"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if len(value) > 0 else "не важно"
    return str(value)


def build_prediction_filter_defaults(criteria_name: str | None = None) -> dict:
    """Возвращает defaults runtime-фильтров top prediction из candidate_criteria.json."""
    defaults = {
        "criteria_name": criteria_name,
        "source": None,
        "country": None,
        "year_min": None,
        "year_max": None,
        "include_genres": [],
        "exclude_genres": [],
        "min_kp_score": None,
        "min_kp_votes": None,
        "min_imdb_score": None,
        "min_imdb_votes": None,
        "only_complete": True,
    }
    if criteria_name is None:
        return defaults

    criteria = load_candidate_criteria().get(criteria_name) or {}
    if isinstance(criteria, dict) is False:
        return defaults

    country = str(criteria.get("country") or "").strip()
    defaults.update({
        "country": country or None,
        "year_min": criteria.get("min_year"),
        "year_max": criteria.get("max_year"),
        "include_genres": list(criteria.get("genres") or []),
        "exclude_genres": list(criteria.get("excluded_genres") or []),
        "min_kp_score": criteria.get("min_kp"),
        "min_kp_votes": criteria.get("min_kp_votes"),
        "min_imdb_score": criteria.get("min_imdb"),
        "min_imdb_votes": criteria.get("min_imdb_votes"),
    })
    return defaults


def format_prediction_filter_default_lines(defaults: dict) -> list[str]:
    """Формирует краткую сводку defaults для экрана top prediction."""
    return [
        f"country: {_format_optional_filter_value(defaults.get('country'))}",
        (
            f"year: {_format_optional_filter_value(defaults.get('year_min'))}"
            f"..{_format_optional_filter_value(defaults.get('year_max'))}"
        ),
        f"include genres (saved pool / KP-IMDb-TMDb data): {_format_optional_filter_value(defaults.get('include_genres'))}",
        f"exclude genres (saved pool / KP-IMDb-TMDb data): {_format_optional_filter_value(defaults.get('exclude_genres'))}",
        f"min KP: {_format_optional_filter_value(defaults.get('min_kp_score'))}",
        f"min KP votes: {_format_optional_filter_value(defaults.get('min_kp_votes'))}",
        f"min IMDb: {_format_optional_filter_value(defaults.get('min_imdb_score'))}",
        f"min IMDb votes: {_format_optional_filter_value(defaults.get('min_imdb_votes'))}",
    ]


def collect_prediction_genre_options(candidates: list) -> list[str]:
    """Returns unique saved-pool genre labels for runtime top prediction filters."""
    seen_keys = set()
    options = []
    for candidate in candidates:
        normalized = normalize_candidate_record(candidate)
        for genre_key in normalized.get("genre_keys") or []:
            if genre_key in seen_keys:
                continue
            label = genre_schema.GENRE_KEY_TO_DISPLAY.get(genre_key)
            if label is None:
                continue
            seen_keys.add(genre_key)
            options.append(label)
    return sorted(options, key=lambda value: str(value).casefold())


def _normalized_optional_text(value) -> str:
    return str(value or "").strip().casefold()


def _candidate_list_values(candidate: dict, field_name: str) -> list[str]:
    values = []
    for item in candidate.get(field_name, []) or []:
        text = str(item or "").strip()
        if text != "":
            values.append(text)
    return values


def _matches_optional_country(candidate: dict, country_filter) -> bool:
    required_codes = country_schema.normalize_country_filter_list(country_filter)
    has_country_filter = False
    if isinstance(country_filter, str):
        has_country_filter = country_filter.strip() != ""
    elif isinstance(country_filter, (list, tuple, set)):
        has_country_filter = any(str(item or "").strip() for item in country_filter)
    elif country_filter not in (None, ""):
        has_country_filter = True
    if has_country_filter and len(required_codes) == 0:
        return False
    if len(required_codes) == 0:
        return True

    candidate_codes = _candidate_list_values(candidate, "country_codes")
    if len(candidate_codes) == 0:
        return False
    return country_schema.country_codes_match_any(candidate_codes, required_codes)


def _matches_optional_genres(candidate: dict, include_genres: list[str], exclude_genres: list[str]) -> bool:
    candidate_keys = _candidate_list_values(candidate, "genre_keys")
    exclude_keys = genre_schema.normalize_genre_filter_list(exclude_genres or [])
    if genre_schema.genre_keys_match_none(candidate_keys, exclude_keys) is False:
        return False
    include_raw = include_genres or []
    include_keys = genre_schema.normalize_genre_filter_list(include_raw)
    has_include_filter = any(str(genre or "").strip() for genre in include_raw)
    if has_include_filter and len(include_keys) == 0:
        return False
    if len(include_keys) == 0:
        return True
    return genre_schema.genre_keys_match_any(candidate_keys, include_keys)


def _matches_min_value(candidate: dict, field_name: str, min_value) -> bool:
    if min_value is None:
        return True
    current = candidate.get(field_name)
    if current is None or str(current).strip() == "":
        return False
    return current >= min_value


def filter_saved_candidates_for_prediction(candidates: list, filters: dict) -> list:
    """Фильтрует уже сохранённых кандидатов из общего пула перед prediction."""
    criteria_name = filters.get("criteria_name")
    source = filters.get("source")
    country = filters.get("country")
    year_min = filters.get("year_min")
    year_max = filters.get("year_max")
    include_genres = filters.get("include_genres") or []
    exclude_genres = filters.get("exclude_genres") or []
    min_kp_score = filters.get("min_kp_score")
    min_kp_votes = filters.get("min_kp_votes")
    min_imdb_score = filters.get("min_imdb_score")
    min_imdb_votes = filters.get("min_imdb_votes")
    only_complete = filters.get("only_complete", True)

    filtered = []
    for candidate in candidates:
        candidate = normalize_candidate_record(candidate)
        if criteria_name and candidate.get("criteria_name") != criteria_name:
            continue
        if source and candidate.get("source") != source:
            continue
        if _matches_optional_country(candidate, country) is False:
            continue

        year = candidate.get("year")
        if year_min is not None and (year is None or year < year_min):
            continue
        if year_max is not None and (year is None or year > year_max):
            continue

        if _matches_optional_genres(candidate, include_genres, exclude_genres) is False:
            continue

        if _matches_min_value(candidate, "kp_score", min_kp_score) is False:
            continue
        if _matches_min_value(candidate, "kp_votes", min_kp_votes) is False:
            continue
        if _matches_min_value(candidate, "imdb_score", min_imdb_score) is False:
            continue
        if _matches_min_value(candidate, "imdb_votes", min_imdb_votes) is False:
            continue

        if only_complete and schema_is_ready_for_predict(candidate) is False:
            continue

        filtered.append(candidate)

    return filtered


def _has_prediction_value(value) -> bool:
    return value is not None and str(value).strip() != ""


def is_candidate_ready_for_prediction(candidate: dict) -> bool:
    """Проверяет, можно ли безопасно считать обычный предикт для кандидата."""
    return schema_is_ready_for_predict(candidate)


def append_signal(candidate: dict, signal: str) -> None:
    """Добавляет signal кандидату без дублей."""
    signals = candidate.setdefault("signals", [])
    if signal not in signals:
        signals.append(signal)


def is_candidate_incomplete(candidate: dict) -> bool:
    """Проверяет, нужны ли кандидату повторные попытки добора KP."""
    return schema_compute_completeness(candidate)["is_complete"] is False


def get_incomplete_candidates(pool: dict, criteria_name: str | None = None) -> list:
    """Возвращает неполных кандидатов из общего пула, опционально по критерию."""
    return [
        candidate
        for candidate in pool.values()
        if (criteria_name is None or candidate.get("criteria_name") == criteria_name)
        and is_candidate_incomplete(candidate)
    ]


def _criteria_country(criteria_name: str | None) -> str:
    if criteria_name is None:
        return "Россия"

    criteria = load_candidate_criteria().get(criteria_name, {})
    return criteria.get("country") or "Россия"


def _mark_kp_retry_attempt(candidate: dict) -> None:
    candidate["kp_attempts"] = int(candidate.get("kp_attempts") or 0) + 1
    candidate["last_kp_attempt_at"] = datetime.now().isoformat(timespec="seconds")


def retry_kp_enrichment_for_pool(limit: int = 10, criteria_name: str | None = None) -> dict:
    """Повторно добирает KP-данные для неполных кандидатов в общем candidate_pool."""
    from candidates import kp_enrichment

    pool = normalize_storage_pool(load_candidate_pool())
    incomplete_candidates = get_incomplete_candidates(pool, criteria_name=criteria_name)
    selected_candidates = incomplete_candidates[:max(0, int(limit))]
    stats = {
        "incomplete_found": len(incomplete_candidates),
        "attempted": 0,
        "kp_found": 0,
        "kp_not_found": 0,
        "api_errors": 0,
        "became_complete": 0,
        "remaining_incomplete": 0,
    }

    for candidate in selected_candidates:
        stats["attempted"] += 1
        _mark_kp_retry_attempt(candidate)

        country = _criteria_country(candidate.get("criteria_name") or criteria_name)
        queries = kp_enrichment.candidate_kp_queries(candidate, include_alternative_title=True)
        if len(queries) == 0:
            candidate["kp_status"] = "not_found"
            candidate["last_kp_error"] = "empty_query"
            append_signal(candidate, "kp_api_not_found_retry")
            candidate.update(normalize_candidate_record(candidate))
            stats["kp_not_found"] += 1
            continue

        lookup = kp_enrichment.lookup_kp_via_api(
            candidate,
            queries,
            country,
            find_series_raw=api.find_series_raw,
            continue_on_reject=True,
        )

        if lookup["status"] == "found":
            kp_enrichment.fill_candidate_from_kp_api(candidate, lookup["movie"] or {})
            candidate["kp_score"] = candidate.get("kp_rating")
            candidate["kp_status"] = "done"
            candidate.pop("last_kp_error", None)
            append_signal(candidate, "kp_api_hit_retry")
            candidate.update(normalize_candidate_record(candidate))
            stats["kp_found"] += 1
            if candidate["is_complete"]:
                stats["became_complete"] += 1
            continue

        if lookup["status"] == "error":
            error_code = lookup.get("error") or "unknown"
            candidate["kp_status"] = "error"
            candidate["last_kp_error"] = error_code
            append_signal(candidate, "kp_api_error_retry")
            candidate.update(normalize_candidate_record(candidate))
            stats["api_errors"] += 1
            continue

        last_error = lookup.get("error") or "not_found"
        reject_reason = lookup.get("reject_reason")
        if reject_reason:
            last_error = f"rejected_{reject_reason}"
            append_signal(candidate, f"kp_api_retry_rejected_{reject_reason}")

        candidate["kp_status"] = "not_found"
        candidate["last_kp_error"] = last_error
        append_signal(candidate, "kp_api_not_found_retry")
        candidate.update(normalize_candidate_record(candidate))
        stats["kp_not_found"] += 1

    stats["remaining_incomplete"] = len(get_incomplete_candidates(pool, criteria_name=criteria_name))
    if stats["attempted"] > 0:
        save_candidate_pool(pool)
    return stats


def remove_candidate_from_pool(target_candidate: dict) -> int:
    """Удаляет из общего пула все варианты кандидата, совпадающие по названию и году."""
    pool = normalize_storage_pool(load_candidate_pool())
    filtered_pool = {}
    removed = 0

    for key, candidate in pool.items():
        if candidates_are_same(candidate, target_candidate, include_criteria=False):
            removed += 1
            continue
        filtered_pool[key] = candidate

    if removed > 0:
        save_candidate_pool(filtered_pool)
    return removed


def build_candidate_features(candidate: dict) -> dict:
    """Собирает признаки модели для кандидата из пула без вайб-тегов."""
    year = int(candidate.get("year") or constant.NOW_YEAR)
    raw_scores = {
        "kp_score": float(candidate.get("kp_score") or 0),
        "kp_votes": int(candidate.get("kp_votes") or 0),
        "imdb_score": float(candidate.get("imdb_score") or 0),
        "imdb_votes": int(candidate.get("imdb_votes") or 0),
    }
    main_info = {"year": year}

    genre_features = {feature: 0 for feature in constant.GENRE}
    for genre_name in candidate.get("genres", []):
        feature = genre_tags.genre_to_feature_name(genre_name)
        if feature in genre_features:
            genre_features[feature] = 1

    features = {constant.BIAS_FEATURE: 1.0}
    features.update(format_score.raw_to_struct(raw_scores, main_info))
    features.update({feature: 0 for feature in constant.TAGS_VIBE})
    features.update(format_score.tags_to_features(genre_features, constant.GENRE_SECTION))
    return features


def find_suspicious_duplicates() -> list:
    """Ищет подозрительно похожие пары кандидатов в общем пуле."""
    candidates = get_all_candidates()
    suspicious_pairs = []

    for left_index in range(len(candidates)):
        left = candidates[left_index]
        left_title = candidate_title(left)
        left_year = left.get("year") or ""
        if left_title == "":
            continue

        for right_index in range(left_index + 1, len(candidates)):
            right = candidates[right_index]
            right_title = candidate_title(right)
            right_year = right.get("year") or ""
            if right_title == "":
                continue
            if left_year != right_year:
                continue

            left_normalized = normalized_title_key(left_title)
            right_normalized = normalized_title_key(right_title)
            if left_normalized == right_normalized:
                continue

            ratio = SequenceMatcher(
                None,
                compact_title_key(left_title),
                compact_title_key(right_title),
            ).ratio()

            if ratio < 0.80:
                continue

            suspicious_pairs.append({
                "left": left,
                "right": right,
                "ratio": ratio,
            })

    suspicious_pairs.sort(key=lambda item: item["ratio"], reverse=True)
    return suspicious_pairs


def rank_candidates_by_predict(candidates: list, weights: dict) -> list:
    """Ранжирует кандидатов по предикту модели без вайб-тегов."""
    from model import model

    no_vibe_features = [
        feature for feature in constant.FEATURES
        if feature not in constant.TAGS_VIBE
    ]
    prediction_weights = model.make_group_weights(weights, no_vibe_features)

    scored_candidates = []
    for candidate in candidates:
        normalized_candidate = normalize_candidate_record(candidate)
        features = build_candidate_features(candidate)
        predict = model.predict_score(features, prediction_weights)
        row = dict(normalized_candidate)
        row.update({
            "title": normalized_candidate.get("title") or "Без названия",
            "year": normalized_candidate.get("year") or "?",
            "predict": predict,
            "predict_score": predict,
        })
        scored_candidates.append(row)

    scored_candidates.sort(key=lambda item: item["predict"], reverse=True)
    return scored_candidates


def _safe_rank_float(value) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _candidate_prediction_score(candidate: dict) -> float | None:
    raw = candidate.get("predict")
    if raw in (None, ""):
        raw = candidate.get("predict_score")
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _filled_score_votes_count(candidate: dict) -> int:
    count = 0
    for field_name in ("kp_score", "kp_votes", "imdb_score", "imdb_votes", "tmdb_score", "tmdb_votes"):
        if candidate.get(field_name) not in (None, ""):
            count += 1
    return count


def _prediction_duplicate_tiebreak_key(candidate: dict, order_index: int) -> tuple:
    return (
        1 if schema_is_ready_for_predict(candidate) else 0,
        1 if candidate.get("is_complete") is True else 0,
        _filled_score_votes_count(candidate),
        _safe_rank_float(candidate.get("final_score")),
        _safe_rank_float(candidate.get("quality_score")),
        _safe_rank_float(candidate.get("kp_score")),
        _safe_rank_float(candidate.get("imdb_score")),
        -order_index,
    )


def _is_better_prediction_duplicate(
    challenger: dict,
    incumbent: dict,
    challenger_index: int,
    incumbent_index: int,
) -> bool:
    challenger_predict = _candidate_prediction_score(challenger)
    incumbent_predict = _candidate_prediction_score(incumbent)

    if challenger_predict is not None and incumbent_predict is not None:
        if challenger_predict != incumbent_predict:
            return challenger_predict > incumbent_predict
    elif challenger_predict is not None:
        return True
    elif incumbent_predict is not None:
        return False

    return _prediction_duplicate_tiebreak_key(challenger, challenger_index) > _prediction_duplicate_tiebreak_key(
        incumbent,
        incumbent_index,
    )


def dedupe_ranked_predictions_by_title_identity(ranked_candidates: list) -> list:
    """Keeps one best candidate per normalized title/year for top prediction display."""
    best_by_identity: dict[str, dict] = {}
    best_index_by_identity: dict[str, int] = {}
    order: list[str] = []

    for index, candidate in enumerate(ranked_candidates):
        identity = title_identity_key(candidate)
        if identity == "|":
            identity = f"__row_{index}"

        current = best_by_identity.get(identity)
        if current is None:
            best_by_identity[identity] = candidate
            best_index_by_identity[identity] = index
            order.append(identity)
            continue

        if _is_better_prediction_duplicate(
            candidate,
            current,
            index,
            best_index_by_identity[identity],
        ):
            best_by_identity[identity] = candidate
            best_index_by_identity[identity] = index

    deduped = [best_by_identity[identity] for identity in order]
    deduped.sort(
        key=lambda item: _candidate_prediction_score(item) if _candidate_prediction_score(item) is not None else float("-inf"),
        reverse=True,
    )
    return deduped


def format_candidate_description(candidate: dict, limit: int = 200) -> str:
    """Returns a short saved description without network requests."""
    for field_name in ("description", "overview", "tmdb_overview", "plot", "short_description"):
        text = str(candidate.get(field_name) or "").strip()
        if text:
            text = " ".join(text.split())
            if len(text) <= limit:
                return text
            return text[: max(0, limit - 3)].rstrip() + "..."
    return "нет данных"


def select_ready_candidates_for_contributions(candidates: list) -> list:
    """Возвращает кандидатов, безопасных для расчёта feature contributions."""
    return [
        candidate for candidate in candidates
        if schema_is_ready_for_predict(candidate)
    ]


def candidate_not_ready_for_contributions_message(candidate: dict) -> str | None:
    """Возвращает понятное сообщение, если кандидат не готов для contributions."""
    if schema_is_ready_for_predict(candidate):
        return None

    missing_fields = schema_compute_completeness(candidate).get("missing_fields") or []
    if len(missing_fields) == 0:
        missing_text = "неизвестно"
    else:
        missing_text = ", ".join(missing_fields)

    return (
        "Кандидат ещё не готов для predict/contributions: не хватает данных. "
        f"Не хватает: {missing_text}."
    )


def candidate_feature_contributions(candidate: dict, weights: dict) -> dict:
    """Считает вклад каждого признака в предикт кандидата без вайб-тегов."""
    from model import model

    no_vibe_features = [
        feature for feature in constant.FEATURES
        if feature not in constant.TAGS_VIBE
    ]
    prediction_weights = model.make_group_weights(weights, no_vibe_features)
    features = build_candidate_features(candidate)
    predict = model.predict_score(features, prediction_weights)

    contributions = []
    for feature in no_vibe_features:
        value = features.get(feature, 0)
        weight = prediction_weights.get(feature, 0)
        impact = value * weight
        if impact == 0 and feature != constant.BIAS_FEATURE:
            continue
        contributions.append({
            "feature": feature,
            "label": constant.FIELD_LABELS.get(feature, feature),
            "value": value,
            "weight": weight,
            "impact": impact,
        })

    positive = sorted(
        [row for row in contributions if row["impact"] > 0],
        key=lambda row: row["impact"],
        reverse=True,
    )
    negative = sorted(
        [row for row in contributions if row["impact"] < 0],
        key=lambda row: row["impact"],
    )

    return {
        "title": candidate.get("title") or "Без названия",
        "year": candidate.get("year") or "?",
        "criteria_name": candidate.get("criteria_name") or "",
        "predict": predict,
        "positive": positive,
        "negative": negative,
    }


def build_contribution_reports_for_ready_candidates(candidates: list, weights: dict) -> list:
    """Считает contributions только для prediction-ready кандидатов."""
    return [
        candidate_feature_contributions(candidate, weights)
        for candidate in select_ready_candidates_for_contributions(candidates)
    ]
