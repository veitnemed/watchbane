"""Собирает и хранит пул кандидатов по сохраненным критериям."""

import json
import os
import time
from datetime import datetime
from difflib import SequenceMatcher

from config import constant
from config import genre_tags
from common import format_score
from apis import api

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
    if isinstance(data, dict) is False:
        return {}
    normalized = remove_watched_candidates(deduplicate_pool(data))
    if normalized != data:
        save_candidate_pool(normalized)
    return normalized


def save_candidate_pool(data: dict) -> None:
    """Сохраняет пул кандидатов."""
    data = remove_watched_candidates(deduplicate_pool(data))
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

    pool = load_candidate_pool()
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
    title = normalized_title_key(
        movie.get("name")
        or movie.get("title")
        or movie.get("alternativeName")
        or movie.get("alternative_title")
        or movie.get("enName")
        or ""
    )
    year = movie.get("year") or ""
    return f"{title}|{year}"


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
    title = normalized_title_key(candidate.get("title") or candidate.get("alternative_title") or "")
    year = candidate.get("year") or ""
    criteria_name = candidate.get("criteria_name") or ""
    return f"{criteria_name}|{title}|{year}"


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
    best_candidates = []
    for candidate in pool.values():
        matched_index = None
        for idx, current_best in enumerate(best_candidates):
            if candidates_are_same(candidate, current_best, include_criteria=True):
                matched_index = idx
                break

        if matched_index is None:
            best_candidates.append(candidate)
            continue

        current_best = best_candidates[matched_index]
        if candidate_sort_score(candidate) > candidate_sort_score(current_best):
            best_candidates[matched_index] = candidate

    deduplicated = {}
    for candidate in best_candidates:
        deduplicated[candidate_key(candidate)] = candidate
    return deduplicated


def build_watched_signatures() -> set:
    """Собирает сигнатуры уже просмотренных объектов из основного датасета."""
    from data_work import storage

    dataset = storage.load_dataset()
    signatures = set()
    for movie in dataset.values():
        main_info = movie.get("main_info", {})
        title = normalized_title_key(main_info.get("title"))
        year = main_info.get("year") or ""
        if title != "":
            signatures.add(f"{title}|{year}")
    return signatures


def is_watched_candidate(candidate: dict, watched_signatures: set | None = None) -> bool:
    """Проверяет, есть ли кандидат уже в основном датасете."""
    if watched_signatures is None:
        watched_signatures = build_watched_signatures()

    title = normalized_title_key(candidate.get("title") or candidate.get("alternative_title") or "")
    year = candidate.get("year") or ""
    exact_signature = f"{title}|{year}"
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
    return {
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
    }


def collect_candidates(criteria_name: str, criteria: dict) -> dict:
    """Собирает новых кандидатов из API по критериям."""
    pool = load_candidate_pool()
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

            key = candidate_key(movie)
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
    pool = load_candidate_pool()
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
    pool = load_candidate_pool()
    candidates = list(pool.values())
    candidates.sort(
        key=lambda item: (
            -(item.get("kp_score") or 0),
            -(item.get("kp_votes") or 0),
            str(item.get("title") or "")
        )
    )
    return candidates


def _normalized_optional_text(value) -> str:
    return str(value or "").strip().casefold()


def _candidate_list_values(candidate: dict, field_name: str) -> list[str]:
    values = []
    for item in candidate.get(field_name, []) or []:
        text = str(item or "").strip()
        if text != "":
            values.append(text)
    return values


def _matches_optional_country(candidate: dict, country_filter: str | None) -> bool:
    expected = _normalized_optional_text(country_filter)
    if expected == "":
        return True

    countries = [_normalized_optional_text(item) for item in _candidate_list_values(candidate, "countries")]
    if len(countries) == 0:
        return False

    for country in countries:
        if country == expected:
            return True
        if expected in country or country in expected:
            return True
    return False


def _matches_optional_genres(candidate: dict, include_genres: list[str], exclude_genres: list[str]) -> bool:
    candidate_genres = {_normalized_optional_text(item) for item in _candidate_list_values(candidate, "genres")}
    candidate_genres.discard("")

    include = {_normalized_optional_text(item) for item in include_genres or []}
    include.discard("")
    exclude = {_normalized_optional_text(item) for item in exclude_genres or []}
    exclude.discard("")

    if len(exclude & candidate_genres) > 0:
        return False
    if len(include) == 0:
        return True
    return len(include & candidate_genres) > 0


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
    min_tmdb_score = filters.get("min_tmdb_score")
    min_tmdb_votes = filters.get("min_tmdb_votes")
    only_complete = filters.get("only_complete", True)

    filtered = []
    for candidate in candidates:
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
        if _matches_min_value(candidate, "tmdb_score", min_tmdb_score) is False:
            continue
        if _matches_min_value(candidate, "tmdb_votes", min_tmdb_votes) is False:
            continue

        if only_complete and "is_complete" in candidate and candidate.get("is_complete") is not True:
            continue

        filtered.append(candidate)

    return filtered


def _has_prediction_value(value) -> bool:
    return value is not None and str(value).strip() != ""


def is_candidate_ready_for_prediction(candidate: dict) -> bool:
    """Проверяет, можно ли безопасно считать обычный предикт для кандидата."""
    has_all_prediction_fields = (
        _has_prediction_value(candidate.get("kp_score"))
        and _has_prediction_value(candidate.get("kp_votes"))
        and _has_prediction_value(candidate.get("imdb_score"))
        and _has_prediction_value(candidate.get("imdb_votes"))
    )
    if has_all_prediction_fields is False:
        return False

    if "is_complete" in candidate:
        return candidate.get("is_complete") is True

    return True


def append_signal(candidate: dict, signal: str) -> None:
    """Добавляет signal кандидату без дублей."""
    signals = candidate.setdefault("signals", [])
    if signal not in signals:
        signals.append(signal)


def is_candidate_incomplete(candidate: dict) -> bool:
    """Проверяет, нужны ли кандидату повторные попытки добора KP."""
    return (
        candidate.get("is_complete") is False
        or candidate.get("kp_score") is None
        or candidate.get("kp_votes") is None
        or candidate.get("kp_status") in {"not_found", "pending_limit", "error"}
    )


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
    from data_work import tmdb_candidate_pool

    pool = load_candidate_pool()
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
        queries = tmdb_candidate_pool.unique_non_empty([
            candidate.get("title"),
            candidate.get("original_title"),
            candidate.get("alternative_title"),
        ])
        year = tmdb_candidate_pool.candidate_year(candidate)
        if len(queries) == 0:
            candidate["kp_status"] = "not_found"
            candidate["is_complete"] = False
            candidate["last_kp_error"] = "empty_query"
            append_signal(candidate, "kp_api_not_found_retry")
            stats["kp_not_found"] += 1
            continue

        found = False
        last_error = None
        for query in queries:
            result = api.find_series_raw(str(query), country, year=year)
            if result.get("ok") is False:
                error_code = result.get("error") or "unknown"
                if error_code in {"not_found", "country_not_found", "empty_title"}:
                    last_error = error_code
                    continue

                candidate["kp_status"] = "error"
                candidate["is_complete"] = False
                candidate["last_kp_error"] = error_code
                append_signal(candidate, "kp_api_error_retry")
                stats["api_errors"] += 1
                found = True
                break

            movie = result.get("data") or {}
            is_safe, reason = tmdb_candidate_pool.kp_match_is_safe(candidate, movie)
            if is_safe is False:
                last_error = f"rejected_{reason}"
                candidate["kp_status"] = "not_found"
                candidate["is_complete"] = False
                candidate["last_kp_error"] = last_error
                append_signal(candidate, f"kp_api_retry_rejected_{reason}")
                continue

            tmdb_candidate_pool.fill_candidate_from_kp_api(candidate, movie)
            candidate["kp_score"] = candidate.get("kp_rating")
            candidate["kp_status"] = "done"
            candidate["is_complete"] = (
                candidate.get("kp_score") is not None
                and candidate.get("kp_votes") is not None
                and candidate.get("imdb_score") is not None
                and candidate.get("imdb_votes") is not None
            )
            candidate.pop("last_kp_error", None)
            append_signal(candidate, "kp_api_hit_retry")
            stats["kp_found"] += 1
            if candidate["is_complete"]:
                stats["became_complete"] += 1
            found = True
            break

        if found:
            continue

        candidate["kp_status"] = "not_found"
        candidate["is_complete"] = False
        candidate["last_kp_error"] = last_error or "not_found"
        append_signal(candidate, "kp_api_not_found_retry")
        stats["kp_not_found"] += 1

    stats["remaining_incomplete"] = len(get_incomplete_candidates(pool, criteria_name=criteria_name))
    if stats["attempted"] > 0:
        save_candidate_pool(pool)
    return stats


def remove_candidate_from_pool(target_candidate: dict) -> int:
    """Удаляет из общего пула все варианты кандидата, совпадающие по названию и году."""
    pool = load_candidate_pool()
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
        features = build_candidate_features(candidate)
        predict = model.predict_score(features, prediction_weights)
        scored_candidates.append({
            "title": candidate.get("title") or "Без названия",
            "year": candidate.get("year") or "?",
            "predict": predict,
        })

    scored_candidates.sort(key=lambda item: item["predict"], reverse=True)
    return scored_candidates


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
