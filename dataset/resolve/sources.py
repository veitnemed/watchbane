"""External API source helpers for title resolve."""

from dataset.resolve.helpers import unique_preserve_order
from apis import kp_api as api

try:
    from apis import tmdb_api as api_tmdb
except ImportError:  # pragma: no cover - TMDb fallback is optional for old environments.
    api_tmdb = None


def fetch_series_raw(title: str, country: str = "Россия") -> dict:
    """Возвращает сырой результат поиска сериала через KP API."""
    return api.find_series_raw(title, country)


def format_series_lines(api_data: dict) -> list:
    """Возвращает строки для печати найденного объекта KP API."""
    return api.format_api_movie_lines(api_data)


def extract_api_countries(api_data: dict) -> str:
    """Возвращает страны объекта API одной строкой (как для превью)."""
    raw_countries = api_data.get("countries")
    if isinstance(raw_countries, list) is False:
        return "нет данных"
    return ", ".join(api.names_from_list(raw_countries).split(", "))


def search_tmdb_defaults_data(queries: list) -> dict:
    """Ищет TMDb-кандидата для add-flow и возвращает нормализованные данные без падения UI."""
    if api_tmdb is None:
        return {
            "data": None,
            "error": {"ok": False, "error": "tmdb_unavailable", "details": "TMDb module is unavailable"},
            "status": "ошибка",
        }

    last_error = None
    for query in unique_preserve_order(queries):
        try:
            results = api_tmdb.search_tv_by_name(query)
            selected = api_tmdb.choose_best_result(results)
            if selected is None:
                last_error = {"ok": False, "error": "not_found", "details": f"TMDb не нашёл: {query}"}
                continue
            details = api_tmdb.get_tv_details(int(selected["id"]))
            return {
                "data": api_tmdb.normalize_tmdb_tv(details),
                "error": None,
                "status": "найдено",
            }
        except Exception as error:  # noqa: BLE001 - внешний API не должен ронять ручное добавление.
            last_error = {"ok": False, "error": "network_error", "details": str(error)}

    if last_error is None:
        last_error = {"ok": False, "error": "not_found", "details": "TMDb не нашёл объект"}
    status = "не найдено" if last_error.get("error") == "not_found" else "ошибка"
    return {
        "data": None,
        "error": last_error,
        "status": status,
    }
