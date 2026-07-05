"""TMDb helpers for TV search, discover, cached details and CLI probing."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
API_URL = "https://api.themoviedb.org/3"
IMAGE_URL = "https://image.tmdb.org/t/p/original"
DEFAULT_LANGUAGE = "ru-RU"
DEFAULT_REGION = "RU"
DEFAULT_TV_DETAIL_APPENDS = (
    "external_ids",
    "content_ratings",
    "watch/providers",
    "aggregate_credits",
    "keywords",
    "images",
    "translations",
)
LEGACY_TV_DETAIL_APPENDS = (
    "external_ids",
    "content_ratings",
    "watch/providers",
    "credits",
)
TMDB_CACHE_DIR = ROOT_DIR / "data" / "cache" / "tmdb"
DISCOVER_CACHE_DIR = TMDB_CACHE_DIR / "discover"
DETAILS_CACHE_DIR = TMDB_CACHE_DIR / "details"
GENRE_CACHE_DIR = TMDB_CACHE_DIR / "genre"


def find_dotenv(path: str | Path = ".env") -> Path | None:
    env_path = Path(path)
    if env_path.is_absolute() and env_path.is_file():
        return env_path

    candidates = []
    for base in [Path.cwd(), Path(__file__).resolve().parent]:
        candidates.append(base / env_path)
        candidates.extend(parent / env_path for parent in base.parents)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = find_dotenv(path)
    if env_path is None:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "" or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_tmdb_token() -> str:
    for env_file in [".env", ".env.local", "tmdb.env"]:
        load_dotenv(env_file)
    token = os.getenv("TMDB_TOKEN", "").strip()
    if token == "":
        raise RuntimeError("TMDB_TOKEN не найден. Добавьте его в .env.local или переменную окружения.")
    return token


def get_token() -> str:
    return load_tmdb_token()


def ensure_cache_dirs() -> None:
    DISCOVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DETAILS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    GENRE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict[str, Any] | None:
    if path.is_file() is False:
        return None
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def cache_key(path: str, params: dict[str, Any] | None = None) -> str:
    payload = {
        "path": path,
        "params": sorted((params or {}).items()),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def normalize_append_to_response(append_to_response: str | list[str] | tuple[str, ...] | None) -> str:
    if append_to_response is None:
        values = DEFAULT_TV_DETAIL_APPENDS
    elif isinstance(append_to_response, str):
        values = tuple(item.strip() for item in append_to_response.split(","))
    else:
        values = tuple(str(item or "").strip() for item in append_to_response)
    return ",".join(item for item in values if item)


def _tv_details_cache_path(tmdb_id: int, language: str, append_to_response: str) -> Path:
    safe_language = language.replace("-", "_")
    legacy_append = normalize_append_to_response(LEGACY_TV_DETAIL_APPENDS)
    if append_to_response == legacy_append:
        return DETAILS_CACHE_DIR / f"{int(tmdb_id)}_{safe_language}.json"
    append_key = hashlib.sha256(append_to_response.encode("utf-8")).hexdigest()[:12]
    return DETAILS_CACHE_DIR / f"{int(tmdb_id)}_{safe_language}_{append_key}.json"


def tmdb_get(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    token: str | None = None,
) -> dict[str, Any]:
    token = token or load_tmdb_token()
    query = urlencode(params or {}, doseq=True)
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"{API_URL}{normalized_path}"
    if query:
        url = f"{url}?{query}"

    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"TMDB вернул HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Не удалось подключиться к TMDB: {error.reason}") from error

    return json.loads(raw)


def cached_tmdb_get(
    path: str,
    params: dict[str, Any] | None,
    cache_path: Path,
    *,
    force_refresh: bool = False,
    token: str | None = None,
) -> dict[str, Any]:
    ensure_cache_dirs()
    if force_refresh is False:
        cached = read_json(cache_path)
        if cached is not None:
            return cached
    payload = tmdb_get(path, params=params, token=token)
    write_json(cache_path, payload)
    return payload


def search_tv_by_name(
    query: str,
    language: str = DEFAULT_LANGUAGE,
    *,
    token: str | None = None,
) -> list[dict[str, Any]]:
    payload = tmdb_get(
        "/search/tv",
        {
            "query": query,
            "language": language,
            "include_adult": "false",
            "page": 1,
        },
        token=token,
    )
    return payload.get("results") or []


def get_tv_genre_list(
    language: str = "en",
    *,
    force_refresh: bool = False,
    token: str | None = None,
) -> list[dict[str, Any]]:
    """Возвращает список жанров TV с кэшированием по языку."""
    safe_language = str(language).replace("-", "_")
    params = {"language": str(language).strip() or "en"}
    cache_path = GENRE_CACHE_DIR / f"tv_{safe_language}.json"
    payload = cached_tmdb_get(
        "/genre/tv/list",
        params,
        cache_path,
        force_refresh=force_refresh,
        token=token,
    )
    genres = payload.get("genres")
    if isinstance(genres, list) is False:
        return []
    return genres


def search_tv(title: str, token: str) -> list[dict[str, Any]]:
    return search_tv_by_name(title, DEFAULT_LANGUAGE, token=token)


def discover_tv_candidates(
    country: str,
    vote_average_gte: float,
    vote_count_gte: int,
    genres_any: list[int] | None = None,
    without_genres: list[int] | str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    language: str = DEFAULT_LANGUAGE,
    max_pages: int = 5,
    sort_by: str = "vote_count.desc",
    with_genres: str | None = None,
    with_original_language: str | None = None,
    force_refresh: bool = False,
    token: str | None = None,
) -> list[dict[str, Any]]:
    all_results: list[dict[str, Any]] = []
    max_pages = max(1, int(max_pages))
    raw_with_genres = str(with_genres or "").strip()
    raw_without_genres = without_genres.strip() if isinstance(without_genres, str) else ""

    for page in range(1, max_pages + 1):
        params: dict[str, Any] = {
            "with_origin_country": country,
            "vote_average.gte": vote_average_gte,
            "vote_count.gte": vote_count_gte,
            "include_adult": "false",
            "sort_by": sort_by,
            "language": language,
            "page": page,
        }
        if raw_with_genres:
            params["with_genres"] = raw_with_genres
        elif genres_any:
            params["with_genres"] = "|".join(str(item) for item in genres_any)

        if raw_without_genres:
            params["without_genres"] = raw_without_genres
        elif without_genres and isinstance(without_genres, str) is False:
            params["without_genres"] = ",".join(str(item) for item in without_genres)

        if with_original_language:
            params["with_original_language"] = with_original_language
        if year_min is not None:
            params["first_air_date.gte"] = f"{int(year_min)}-01-01"
        if year_max is not None:
            params["first_air_date.lte"] = f"{int(year_max)}-12-31"

        key = cache_key("/discover/tv", params)
        cache_path = DISCOVER_CACHE_DIR / f"{key}.json"
        payload = cached_tmdb_get(
            "/discover/tv",
            params,
            cache_path,
            force_refresh=force_refresh,
            token=token,
        )
        page_results = payload.get("results") or []
        all_results.extend(page_results)

        total_pages = int(payload.get("total_pages") or page)
        if page >= total_pages:
            break

    return all_results


def get_tv_details(
    tmdb_id: int,
    language: str = DEFAULT_LANGUAGE,
    *,
    append_to_response: str | list[str] | tuple[str, ...] | None = None,
    force_refresh: bool = False,
    token: str | None = None,
) -> dict[str, Any]:
    append_value = normalize_append_to_response(append_to_response)
    params = {
        "language": language,
        "append_to_response": append_value,
    }
    cache_path = _tv_details_cache_path(int(tmdb_id), language, append_value)
    return cached_tmdb_get(
        f"/tv/{int(tmdb_id)}",
        params,
        cache_path,
        force_refresh=force_refresh,
        token=token,
    )


def names_from_items(items: list[dict[str, Any]] | None, key: str = "name") -> list[str]:
    names: list[str] = []
    for item in items or []:
        if isinstance(item, dict) is False:
            continue
        value = str(item.get(key) or "").strip()
        if value and value not in names:
            names.append(value)
    return names


def country_codes_from_items(items: list[dict[str, Any]] | None) -> list[str]:
    codes: list[str] = []
    for item in items or []:
        code = str(item.get("iso_3166_1") or "").strip().upper()
        if code and code not in codes:
            codes.append(code)
    return codes


def image_link(path: str | None) -> str | None:
    if not path:
        return None
    return f"{IMAGE_URL}{path}"


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _translation_language_keys(item: dict[str, Any]) -> set[str]:
    language = str(item.get("iso_639_1") or "").strip()
    country = str(item.get("iso_3166_1") or "").strip()
    keys = set()
    if language:
        keys.add(language.casefold())
    if language and country:
        keys.add(f"{language}-{country}".casefold())
    return keys


def _translation_items(raw_details: dict[str, Any]) -> list[dict[str, Any]]:
    translations = raw_details.get("translations") or {}
    items = translations.get("translations") if isinstance(translations, dict) else translations
    return [item for item in items or [] if isinstance(item, dict)]


def extract_best_overview(
    raw_details: dict[str, Any],
    preferred_languages: tuple[str, ...] = ("ru-RU", "ru", "en-US", "en"),
) -> str | None:
    overview = _clean_text(raw_details.get("overview"))
    if overview is not None:
        return overview

    translations = _translation_items(raw_details)
    preferred = [str(language or "").strip().casefold() for language in preferred_languages if str(language or "").strip()]
    for language in preferred:
        for item in translations:
            if language not in _translation_language_keys(item):
                continue
            data = item.get("data") or {}
            overview = _clean_text(data.get("overview")) if isinstance(data, dict) else None
            if overview is not None:
                return overview
    return None


def extract_best_poster_path(raw_details: dict[str, Any]) -> str | None:
    poster_path = _clean_text(raw_details.get("poster_path"))
    if poster_path is not None:
        return poster_path

    posters = (raw_details.get("images") or {}).get("posters") or []
    valid_posters = [item for item in posters if isinstance(item, dict) and _clean_text(item.get("file_path"))]
    if not valid_posters:
        return None

    def poster_rank(item: dict[str, Any]) -> tuple:
        language = str(item.get("iso_639_1") or "").casefold()
        language_rank = {"ru": 3, "en": 2, "": 1, "none": 1}.get(language, 0)
        return (
            language_rank,
            float(item.get("vote_average") or 0),
            int(item.get("vote_count") or 0),
        )

    return _clean_text(max(valid_posters, key=poster_rank).get("file_path"))


def _person_credit(item: dict[str, Any], role: str | None, episode_count: int | None) -> dict[str, Any] | None:
    name = _clean_text(item.get("name"))
    if name is None:
        return None
    credit = {"name": name}
    if role:
        credit["role"] = role
    if episode_count is not None:
        credit["episode_count"] = episode_count
    if item.get("id") is not None:
        credit["tmdb_person_id"] = item.get("id")
    return credit


def _roles_text(roles: list[dict[str, Any]], role_key: str) -> str | None:
    names = []
    for role in roles:
        if isinstance(role, dict) is False:
            continue
        value = _clean_text(role.get(role_key))
        if value and value not in names:
            names.append(value)
    return ", ".join(names) if names else None


def _episode_count(roles: list[dict[str, Any]]) -> int | None:
    counts = []
    for role in roles:
        if isinstance(role, dict) and role.get("episode_count") is not None:
            try:
                counts.append(int(role.get("episode_count")))
            except (TypeError, ValueError):
                continue
    return sum(counts) if counts else None


def extract_aggregate_credits_top(raw_details: dict[str, Any], limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    aggregate_credits = raw_details.get("aggregate_credits") or {}
    result = {"actors_top": [], "crew_top": []}
    for source_key, target_key, role_key in (
        ("cast", "actors_top", "character"),
        ("crew", "crew_top", "job"),
    ):
        people = aggregate_credits.get(source_key) or []
        normalized_people = []
        for item in people:
            if isinstance(item, dict) is False:
                continue
            roles = item.get("roles") or item.get("jobs") or []
            roles = roles if isinstance(roles, list) else []
            credit = _person_credit(
                item,
                _roles_text(roles, role_key),
                _episode_count(roles),
            )
            if credit is not None:
                normalized_people.append(credit)
        normalized_people.sort(
            key=lambda value: (
                int(value.get("episode_count") or 0),
                str(value.get("name") or "").casefold(),
            ),
            reverse=True,
        )
        result[target_key] = normalized_people[: max(0, int(limit))]
    return result


def extract_keywords(raw_details: dict[str, Any]) -> list[str]:
    keywords = raw_details.get("keywords") or {}
    items = keywords.get("results") or keywords.get("keywords") if isinstance(keywords, dict) else keywords
    result: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            name = _clean_text(item.get("name"))
        else:
            name = _clean_text(item)
        if name and name not in result:
            result.append(name)
    return result


def extract_external_ids(raw_details: dict[str, Any]) -> dict[str, Any]:
    external_ids = raw_details.get("external_ids") or {}
    if isinstance(external_ids, dict) is False:
        return {}
    return {
        key: value
        for key, value in external_ids.items()
        if value is not None and str(value).strip() != ""
    }


def get_content_rating(details: dict[str, Any], region: str = DEFAULT_REGION) -> str | None:
    ratings = details.get("content_ratings", {}).get("results") or []
    for item in ratings:
        if item.get("iso_3166_1") == region and item.get("rating"):
            return item["rating"]
    for item in ratings:
        if item.get("rating"):
            return f"{item.get('iso_3166_1')}: {item.get('rating')}"
    return None


def get_watch_providers(details: dict[str, Any], region: str = DEFAULT_REGION) -> list[str]:
    region_data = details.get("watch/providers", {}).get("results", {}).get(region) or {}
    names: list[str] = []
    for section in ("flatrate", "free", "ads", "rent", "buy"):
        for provider in region_data.get(section) or []:
            name = provider.get("provider_name")
            if name and name not in names:
                names.append(name)
    return names


def get_ru_content_rating(details: dict[str, Any]) -> str:
    return get_content_rating(details, DEFAULT_REGION) or "-"


def get_year(date_value: str | None) -> int | None:
    if not date_value:
        return None
    try:
        return int(str(date_value)[:4])
    except ValueError:
        return None


def normalize_people(items: list[dict[str, Any]] | None, limit: int, role_key: str) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    for person in (items or [])[:limit]:
        if isinstance(person, dict) is False:
            continue
        name = person.get("name")
        if not name:
            continue
        people.append({
            "name": name,
            "role": person.get(role_key),
        })
    return people


def normalize_tmdb_tv(raw_details: dict[str, Any]) -> dict[str, Any]:
    external_ids = extract_external_ids(raw_details)
    credits = raw_details.get("credits") or {}
    aggregate_credits = extract_aggregate_credits_top(raw_details, limit=10)
    first_air_date = raw_details.get("first_air_date")
    production_countries = raw_details.get("production_countries") or []
    poster_path = extract_best_poster_path(raw_details)

    return {
        "tmdb_id": raw_details.get("id"),
        "imdb_id": external_ids.get("imdb_id"),
        "tvdb_id": external_ids.get("tvdb_id"),
        "kp_id": None,
        "title": raw_details.get("name"),
        "original_title": raw_details.get("original_name"),
        "year": get_year(first_air_date),
        "first_air_date": first_air_date,
        "last_air_date": raw_details.get("last_air_date"),
        "status": raw_details.get("status"),
        "type": raw_details.get("type"),
        "in_production": raw_details.get("in_production"),
        "original_language": raw_details.get("original_language"),
        "tmdb_origin_countries": raw_details.get("origin_country") or [],
        "tmdb_production_countries": names_from_items(production_countries),
        "tmdb_country_codes": country_codes_from_items(production_countries),
        "genres_tmdb": names_from_items(raw_details.get("genres")),
        "networks": names_from_items(raw_details.get("networks")),
        "production_companies": names_from_items(raw_details.get("production_companies")),
        "number_of_seasons": raw_details.get("number_of_seasons"),
        "number_of_episodes": raw_details.get("number_of_episodes"),
        "episode_run_time": raw_details.get("episode_run_time"),
        "tmdb_rating": raw_details.get("vote_average"),
        "tmdb_votes": raw_details.get("vote_count"),
        "tmdb_popularity": raw_details.get("popularity"),
        "overview": extract_best_overview(raw_details),
        "poster_path": poster_path,
        "poster_url": image_link(poster_path),
        "backdrop_path": raw_details.get("backdrop_path"),
        "backdrop_url": image_link(raw_details.get("backdrop_path")),
        "content_rating": get_content_rating(raw_details),
        "watch_providers_ru": get_watch_providers(raw_details, DEFAULT_REGION),
        "actors_top": aggregate_credits["actors_top"][:8] or normalize_people(credits.get("cast"), 8, "character"),
        "crew_top": aggregate_credits["crew_top"][:5] or normalize_people(credits.get("crew"), 5, "job"),
        "keywords": extract_keywords(raw_details),
        "imdb_rating": None,
        "imdb_votes": None,
        "imdb_title_type": None,
        "imdb_is_adult": None,
        "imdb_start_year": None,
        "imdb_end_year": None,
        "imdb_runtime_minutes": None,
        "imdb_genres": [],
        "country_score": 0.0,
        "country_signals": [],
        "quality_score": 0.0,
        "hidden_gem_score": 0.0,
        "final_score": 0.0,
        "signals": [],
        "source": "tmdb_discover",
        "source_query": {},
    }


def is_russian_candidate(show: dict[str, Any]) -> bool:
    origin_country = show.get("origin_country") or []
    original_language = show.get("original_language")
    return "RU" in origin_country or original_language == "ru"


def choose_best_result(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    russian_results = [show for show in results if is_russian_candidate(show)]
    candidates = russian_results or results
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.get("vote_count") or 0, item.get("popularity") or 0))


def format_list(values: list[Any] | None) -> str:
    if not values:
        return "-"
    return ", ".join(str(value) for value in values)


def format_people(people: list[dict[str, Any]] | None, limit: int = 8) -> str:
    people = people or []
    names = []
    for person in people[:limit]:
        name = person.get("name")
        role = person.get("role")
        if name and role:
            names.append(f"{name} ({role})")
        elif name:
            names.append(name)
    return ", ".join(names) if names else "-"


def build_report(details: dict[str, Any]) -> list[str]:
    data = normalize_tmdb_tv(details)
    lines = [
        "Основная информация TMDB",
        "=" * 60,
        f"TMDB ID: {data.get('tmdb_id')}",
        f"Название: {data.get('title') or '-'}",
        f"Оригинальное название: {data.get('original_title') or '-'}",
        f"Год старта: {data.get('year') or '-'}",
        f"Первый эфир: {data.get('first_air_date') or '-'}",
        f"Последний эфир: {data.get('last_air_date') or '-'}",
        f"Статус: {data.get('status') or '-'}",
        f"Тип: {data.get('type') or '-'}",
        f"В производстве: {'да' if data.get('in_production') else 'нет'}",
        f"Оригинальный язык: {data.get('original_language') or '-'}",
        f"Страны происхождения: {format_list(data.get('tmdb_origin_countries'))}",
        f"Страны производства: {format_list(data.get('tmdb_production_countries'))}",
        f"Жанры: {format_list(data.get('genres_tmdb'))}",
        f"Сети: {format_list(data.get('networks'))}",
        f"Производство: {format_list(data.get('production_companies'))}",
        f"Сезонов: {data.get('number_of_seasons') or '-'}",
        f"Серий: {data.get('number_of_episodes') or '-'}",
        f"Рейтинг TMDB: {data.get('tmdb_rating') or '-'}",
        f"Голосов TMDB: {data.get('tmdb_votes') or '-'}",
        f"Популярность: {data.get('tmdb_popularity') or '-'}",
        f"Возрастной рейтинг: {data.get('content_rating') or '-'}",
        f"Где смотреть RU: {format_list(data.get('watch_providers_ru'))}",
        f"IMDb ID: {data.get('imdb_id') or '-'}",
        f"TVDB ID: {data.get('tvdb_id') or '-'}",
        f"Постер: {data.get('poster_url') or '-'}",
        f"Фон: {data.get('backdrop_url') or '-'}",
        "",
        "Описание",
        "-" * 60,
        data.get("overview") or "-",
        "",
        "Команда и актёры",
        "-" * 60,
        f"Актёры: {format_people(data.get('actors_top'))}",
        f"Съёмочная группа: {format_people(data.get('crew_top'), 5)}",
    ]
    return lines


def print_search_options(results: list[dict[str, Any]], selected_id: int) -> None:
    print("")
    print("Найденные варианты")
    print("-" * 60)
    for index, item in enumerate(results[:8], start=1):
        marker = "*" if item.get("id") == selected_id else " "
        year = (item.get("first_air_date") or "-")[:4]
        countries = ", ".join(item.get("origin_country") or []) or "-"
        rating = item.get("vote_average") or "-"
        print(f"{marker} {index}. {item.get('name') or '-'} ({year}), {countries}, rating={rating}, id={item.get('id')}")


def check_api_available(token: str | None = None) -> dict[str, Any]:
    """Проверяет базовую доступность TMDb API коротким запросом."""
    try:
        resolved_token = token or load_tmdb_token()
    except RuntimeError as error:
        return {
            "ok": False,
            "error": "missing_token",
            "details": str(error),
        }

    started = time.monotonic()
    try:
        tmdb_get("/configuration", token=resolved_token)
    except RuntimeError as error:
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        return {
            "ok": False,
            "error": "request_failed",
            "details": str(error),
            "elapsed_ms": elapsed_ms,
        }

    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    return {"ok": True, "data": True, "elapsed_ms": elapsed_ms}


def main() -> None:
    token = load_tmdb_token()
    title = input("Название российского сериала на русском >> ").strip()
    if title == "":
        print("Название не задано.")
        return

    results = search_tv_by_name(title, token=token)
    selected = choose_best_result(results)
    if selected is None:
        print("Ничего не найдено.")
        return

    details = get_tv_details(int(selected["id"]), token=token)
    print_search_options(results, selected_id=int(selected["id"]))
    print("")
    for line in build_report(details):
        print(line)


if __name__ == "__main__":
    main()
