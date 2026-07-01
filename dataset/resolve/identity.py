"""SQL/KP/TMDb identity matching for title resolve."""

from difflib import SequenceMatcher

from apis import imdb_sql as sql_search
from dataset.resolve.helpers import (
    add_title_value,
    extract_candidate_imdb_id,
    extract_candidate_year,
    unique_preserve_order,
)


def extract_sql_identity_titles(candidate: dict | None) -> list:
    """Собирает названия SQL-кандидата, по которым можно проверять identity."""
    if not isinstance(candidate, dict):
        return []

    titles = []
    for key in ("title", "original_title", "primaryTitle", "originalTitle"):
        add_title_value(titles, candidate.get(key))

    for item in candidate.get("alternative_titles", []) or []:
        if isinstance(item, dict):
            add_title_value(titles, item.get("title"))
        else:
            add_title_value(titles, item)

    match = candidate.get("match") or {}
    if isinstance(match, dict):
        for item in match.get("matched_titles", []) or []:
            add_title_value(titles, item)

    return titles


def extract_api_identity_titles(candidate: dict | None) -> list:
    """Собирает названия API-кандидата, по которым можно проверять identity."""
    if not isinstance(candidate, dict):
        return []

    titles = []
    for key in ("title", "name", "original_title", "original_name", "originalName", "alternativeName", "enName"):
        add_title_value(titles, candidate.get(key))
    return titles


def normalize_identity_title(value) -> str:
    """Нормализует название для безопасного сравнения identity."""
    return sql_search.normalize_for_match(value).replace("ё", "е")


def title_identity_match(left, right) -> bool:
    """Проверяет, похожи ли два названия достаточно для identity gate."""
    left_norm = normalize_identity_title(left)
    right_norm = normalize_identity_title(right)
    if left_norm == "" or right_norm == "":
        return False
    if left_norm == right_norm:
        return True
    if min(len(left_norm), len(right_norm)) >= 4 and (left_norm in right_norm or right_norm in left_norm):
        return True

    left_translit = sql_search.transliterate_to_latin(left_norm)
    right_translit = sql_search.transliterate_to_latin(right_norm)
    if left_translit and right_translit and left_translit == right_translit:
        return True

    ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
    if ratio >= 0.82:
        return True

    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    common = left_tokens & right_tokens
    if len(common) >= 2:
        return True
    return len(common) == 1 and min(len(left_tokens), len(right_tokens)) == 1


def sql_titles_match_identity(sql_candidate: dict, api_candidate: dict, query: str) -> bool:
    """Проверяет, что SQL title/original похожи на query или API title/original."""
    sql_titles = extract_sql_identity_titles(sql_candidate)
    trusted_titles = extract_api_identity_titles(api_candidate)
    add_title_value(trusted_titles, query)

    for sql_title in sql_titles:
        for trusted_title in trusted_titles:
            if title_identity_match(sql_title, trusted_title):
                return True
    return False


def is_sql_candidate_identity_safe(sql_candidate: dict | None, api_candidate: dict | None, query: str) -> tuple[bool, str]:
    """Решает, можно ли смешивать SQL IMDb candidate с API candidate."""
    if sql_candidate is None:
        return False, "sql_missing"
    if api_candidate is None:
        return True, "sql_only"

    sql_imdb_id = extract_candidate_imdb_id(sql_candidate)
    api_imdb_id = extract_candidate_imdb_id(api_candidate)
    if sql_imdb_id and api_imdb_id:
        if sql_imdb_id == api_imdb_id:
            return True, "imdb_id_match"
        return False, "imdb_id_mismatch"

    sql_year = extract_candidate_year(sql_candidate)
    api_year = extract_candidate_year(api_candidate)
    if sql_titles_match_identity(sql_candidate, api_candidate, query) is False:
        return False, "identity_mismatch"
    if sql_year is not None and api_year is not None and abs(sql_year - api_year) > 1:
        return False, "year_mismatch"

    return True, "title_year_match"


def extract_api_original_title(series: dict | None) -> str:
    """Достаёт original title из API/TMDb candidate для second-pass SQL."""
    if not isinstance(series, dict):
        return ""
    for key in ("original_title", "original_name", "originalName", "alternativeName", "enName"):
        value = str(series.get(key) or "").strip()
        if value:
            return value
    return ""


def iter_sql_result_candidates(sql_result: dict) -> list:
    """Возвращает best + alternatives из SQL-ответа для проверки identity."""
    if not isinstance(sql_result, dict) or sql_result.get("ok") is not True:
        return []

    candidates = []
    data = sql_result.get("data")
    if isinstance(data, dict):
        candidates.append(data)
        for alternative in data.get("alternatives", []) or []:
            if isinstance(alternative, dict):
                candidates.append(alternative)
    return candidates


def resolve_sql_after_api_mismatch(query: str, api_candidate: dict, country: str = "Россия", sql_search_func=None) -> dict:
    """Ищет SQL-кандидата заново по API identity после reject первого SQL."""
    from dataset.resolve.defaults import extract_api_title, has_api_imdb_values

    sql_search_func = sql_search_func or sql_search.search_title_in_sql
    attempts = []

    imdb_id = extract_candidate_imdb_id(api_candidate)
    imdb_id_search = getattr(sql_search, "search_title_by_imdb_id", None)
    if imdb_id:
        if callable(imdb_id_search):
            sql_result = imdb_id_search(imdb_id)
            attempts.append({"method": "imdb_id", "query": imdb_id, "result": sql_result})
            for candidate in iter_sql_result_candidates(sql_result):
                accepted, reason = is_sql_candidate_identity_safe(candidate, api_candidate, query)
                if accepted:
                    return {
                        "data": candidate,
                        "identity": {"accepted": True, "reason": reason},
                        "status": "найдено и принято",
                        "attempts": attempts,
                    }
        else:
            attempts.append({"method": "imdb_id", "query": imdb_id, "result": {"ok": False, "error": "unsupported"}})

    api_title = extract_api_title(api_candidate)
    api_original_title = extract_api_original_title(api_candidate)
    search_titles = unique_preserve_order([api_title, api_original_title])
    last_identity = None
    found_rejected = False

    for search_title in search_titles:
        sql_result = sql_search_func(search_title, country)
        attempt = {"method": "title_year", "query": search_title, "result": sql_result}
        attempts.append(attempt)
        if sql_result.get("ok") is not True:
            continue

        for candidate in iter_sql_result_candidates(sql_result):
            accepted, reason = is_sql_candidate_identity_safe(candidate, api_candidate, query)
            last_identity = {"accepted": accepted, "reason": reason}
            if accepted:
                attempt["accepted_candidate"] = candidate
                return {
                    "data": candidate,
                    "identity": last_identity,
                    "status": "найдено и принято",
                    "attempts": attempts,
                }
            found_rejected = True

    if found_rejected:
        return {
            "data": None,
            "identity": last_identity,
            "status": f"найдено, но отклонено ({last_identity.get('reason')})",
            "attempts": attempts,
        }

    return {
        "data": None,
        "identity": None,
        "status": "не найдено",
        "attempts": attempts,
    }
