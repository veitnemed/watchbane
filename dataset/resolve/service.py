"""Main add-flow resolve orchestration."""

from config import scheme
from dataset.resolve.defaults import has_api_imdb_values
from dataset.resolve.helpers import unique_preserve_order
from dataset.resolve.identity import is_sql_candidate_identity_safe, resolve_sql_after_api_mismatch
from dataset.resolve.priority import build_add_defaults_by_priority
from dataset.resolve.sources import search_tmdb_defaults_data
from dataset.resolve.status import get_kp_status, get_sql_status
from apis import imdb_sql as sql_search
from apis import kp_api as api

ADD_TITLE_RESOLVE_PROGRESS_TOTAL = 7


def print_progress_step(source: str, status: str) -> None:
    print(f"{source}: {status}")


def _report_add_progress(
    on_progress,
    step: int,
    source: str,
    status: str,
) -> None:
    message = f"{source}: {status}"
    if on_progress is not None:
        on_progress(step, ADD_TITLE_RESOLVE_PROGRESS_TOTAL, message)
        return
    print_progress_step(source, status)


def resolve_title_data_for_add(
    title: str,
    country: str = "Россия",
    *,
    on_progress=None,
) -> dict:
    """Собирает defaults для добавления записи по приоритетам SQL -> KP -> TMDb -> ручной ввод."""
    title = api.normalize_text(title)
    country = api.normalize_text(country)

    _report_add_progress(on_progress, 1, "IMDb dataset", "Поиск")
    sql_result = sql_search.search_title_in_sql(title, country)
    sql_data = sql_result["data"] if sql_result["ok"] else None
    _report_add_progress(
        on_progress,
        2,
        "IMDb dataset",
        "Успешно" if sql_data is not None else "Нет кандидатов",
    )

    api_data = None
    last_api_error = None
    api_queries = unique_preserve_order([
        title,
        (sql_data or {}).get("title"),
        (sql_data or {}).get("original_title"),
    ])
    _report_add_progress(on_progress, 3, "KP API", "Ожидание ответа")
    for query in api_queries:
        api_result = api.find_series_raw(query, country)
        if api_result["ok"]:
            api_data = api_result["data"]
            break
        last_api_error = api_result
    kp_status = get_kp_status(api_data, last_api_error)
    if kp_status == "найдено":
        _report_add_progress(on_progress, 4, "KP API", "Успешно")
    elif kp_status == "ошибка":
        _report_add_progress(on_progress, 4, "KP API", "Ошибка сети")
    else:
        _report_add_progress(on_progress, 4, "KP API", "Нет кандидатов")

    tmdb_data = None
    tmdb_error = None
    tmdb_status = "не найдено"
    if api_data is None:
        _report_add_progress(on_progress, 5, "TMDb API", "Ожидание ответа")
        tmdb_result = search_tmdb_defaults_data(api_queries)
        tmdb_data = tmdb_result["data"]
        tmdb_error = tmdb_result["error"]
        tmdb_status = tmdb_result["status"]
        if tmdb_status == "найдено":
            _report_add_progress(on_progress, 6, "TMDb API", "Успешно")
        elif tmdb_status == "ошибка":
            _report_add_progress(on_progress, 6, "TMDb API", "Ошибка сети")
        else:
            _report_add_progress(on_progress, 6, "TMDb API", "Нет кандидатов")
    else:
        _report_add_progress(on_progress, 5, "TMDb API", "Не требуется")
        _report_add_progress(on_progress, 6, "TMDb API", "Не требуется")

    api_identity_candidate = api_data if api_data is not None else tmdb_data
    sql_first_identity = None
    sql_second_pass_result = None
    sql_second_pass_data = None
    sql_second_pass_identity = None
    sql_second_pass_status = None
    sql_merge_data = sql_data
    sql_merge_source = "imdb_sql"

    if sql_data is not None and api_identity_candidate is not None:
        accepted, reason = is_sql_candidate_identity_safe(sql_data, api_identity_candidate, title)
        sql_first_identity = {"accepted": accepted, "reason": reason}
        if accepted is False:
            if has_api_imdb_values(api_data):
                sql_second_pass_status = "не требуется, IMDb взят из KP API"
            else:
                sql_second_pass_result = resolve_sql_after_api_mismatch(title, api_identity_candidate, country)
                sql_second_pass_data = sql_second_pass_result.get("data")
                sql_second_pass_identity = sql_second_pass_result.get("identity")
                sql_second_pass_status = sql_second_pass_result.get("status")
                if sql_second_pass_data is not None:
                    sql_merge_data = sql_second_pass_data
                    sql_merge_source = "imdb_sql_second_pass"

    found = sql_data is not None or api_data is not None or tmdb_data is not None
    defaults = None
    sources = {}
    source_values = {}
    sql_identity = None
    if found:
        built = build_add_defaults_by_priority(title, sql_merge_data, api_data, tmdb_data, sql_merge_source)
        defaults = built["defaults"]
        if defaults[scheme.MAIN_INFO].get("country") in (None, ""):
            defaults[scheme.MAIN_INFO]["country"] = country
        sources = built["sources"]
        if sources.get("country") is None:
            sources["country"] = "input"
        source_values = built["source_values"]
        sql_identity = sql_first_identity or built["sql_identity"]

    statuses = {
        "sql": get_sql_status(sql_data, sql_identity),
        "kp_api": get_kp_status(api_data, last_api_error),
        "tmdb_api": tmdb_status,
    }
    if sql_second_pass_status is not None:
        statuses["sql_second_pass"] = sql_second_pass_status

    _report_add_progress(on_progress, 7, "Подготовка", "Готово")

    return {
        "title": title,
        "country": country,
        "sql_result": sql_result,
        "sql_data": sql_data,
        "sql_merge_data": sql_merge_data,
        "sql_merge_source": sql_merge_source,
        "sql_second_pass_result": sql_second_pass_result,
        "sql_second_pass_data": sql_second_pass_data,
        "sql_second_pass_identity": sql_second_pass_identity,
        "api_data": api_data,
        "api_error": last_api_error,
        "tmdb_data": tmdb_data,
        "tmdb_error": tmdb_error,
        "defaults": defaults,
        "sources": sources,
        "source_values": source_values,
        "sql_identity": sql_identity,
        "statuses": statuses,
        "found": found,
    }


def resolve_title_data(title: str, country: str = "Россия") -> dict:
    """Совместимое имя: add-flow использует единые приоритеты источников."""
    return resolve_title_data_for_add(title, country)
