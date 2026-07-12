"""Build TMDb genre distribution report for dataset titles with local cache."""

from __future__ import annotations

import argparse
import json
import re
import socket
import unicodedata
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit
from urllib.request import getproxies


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from storage import data as storage_data
from apis import tmdb_api as api_tmdb


TMDB_GENRE_CACHE_PATH = ROOT_DIR / "data" / "cache" / "tmdb" / "tmdb_genre.json"
REPORT_DIR = ROOT_DIR / "reports" / "quality" / "genre"
STATUS_MATCHED = "matched"
STATUS_NOT_FOUND = "not_found"
STATUS_NO_GENRES = "no_genres"
STATUS_NETWORK_ERROR = "network_error"
STATUS_SKIPPED_CACHED = "skipped_cached"
RETRIABLE_CACHE_STATUSES = {STATUS_NETWORK_ERROR}
TMDB_DIAGNOSTIC_HOSTS = ("api.themoviedb.org", "www.themoviedb.org")


def _safe_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_cache_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(title or "").strip().casefold())
    normalized = re.sub(r"[^\w\d\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _build_cache_key(title: str, year: int | None) -> str:
    return f"{_normalize_cache_title(title)}|{year}"


def _safe_year(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_file() is False:
        return {}
    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _find_nested_value(data: Any, key: str):
    if isinstance(data, dict) is False:
        return None
    if key in data and data[key] not in ("", None):
        return data[key]
    for value in data.values():
        if isinstance(value, dict):
            found = _find_nested_value(value, key)
            if found not in ("", None):
                return found
        elif isinstance(value, list):
            for item in value:
                found = _find_nested_value(item, key)
                if found not in ("", None):
                    return found
    return None


def _redact_proxy_url(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if value == "":
        return "-"
    parsed = urlsplit(value if "://" in value else f"http://{value}")
    host = parsed.hostname or value
    port = f":{parsed.port}" if parsed.port else ""
    scheme = parsed.scheme or "http"
    return f"{scheme}://{host}{port}"


def _tmdb_network_diagnostics() -> list[str]:
    lines: list[str] = []
    for host in TMDB_DIAGNOSTIC_HOSTS:
        try:
            infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            addresses = sorted({str(info[4][0]) for info in infos})
        except OSError as error:
            lines.append(f"{host}: ошибка DNS-запроса: {error}")
            continue

        if addresses:
            joined = ", ".join(addresses)
            lines.append(f"{host}: резолвится в {joined}")
            if any(address == "::1" or address.startswith("127.") for address in addresses):
                lines.append(f"{host}: ВНИМАНИЕ, резолвится в localhost; проверь DNS/proxy/VPN-маршрутизацию.")
        else:
            lines.append(f"{host}: DNS-запрос не вернул адресов.")

    proxies = getproxies()
    if proxies:
        safe_proxies = ", ".join(
            f"{name}={_redact_proxy_url(value)}"
            for name, value in sorted(proxies.items())
        )
        lines.append(f"Proxy-настройки Python: {safe_proxies}")
    else:
        lines.append("Proxy-настройки Python: нет")
    return lines


def _extract_tmdb_id(meta_obj: dict[str, Any] | None) -> int | None:
    if isinstance(meta_obj, dict) is False:
        return None
    tmdb_id = (
        meta_obj.get("tmdb_id")
        or _find_nested_value(meta_obj.get("tmdb_data"), "tmdb_id")
        or _find_nested_value(meta_obj.get("tmdb_data"), "id")
        or _find_nested_value(meta_obj.get("source_values"), "tmdb_id")
    )
    return _safe_int(tmdb_id)


def _extract_dataset_title_and_year(title: str, record: dict[str, Any]) -> tuple[str, int | None]:
    main_info = record.get("main_info") if isinstance(record, dict) else {}
    record_title = str((main_info or {}).get("title") or title or "").strip()
    year = _safe_year((main_info or {}).get("year"))
    return record_title, year


def _find_meta_obj(meta: dict[str, Any], title: str) -> dict[str, Any]:
    if title in meta:
        return meta.get(title)
    normalized_target = _normalize_cache_title(title)
    for key, value in meta.items():
        if _normalize_cache_title(str(key)) == normalized_target:
            return value
    return {}


def _extract_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if len(text) == 4 and text.isdigit():
        return int(text)
    if "-" in text:
        try:
            return int(text.split("-", 1)[0])
        except ValueError:
            return None
    return None


def _official_genre_map(language: str, *, force_refresh: bool) -> tuple[dict[int, str], list[dict[str, Any]]]:
    official_genres = api_tmdb.get_tv_genre_list(language, force_refresh=force_refresh)
    by_id: dict[int, str] = {}
    for item in official_genres:
        if isinstance(item, dict) is False:
            continue
        genre_id = _safe_int(item.get("id"))
        name = item.get("name")
        if genre_id is None or not str(name).strip():
            continue
        by_id[genre_id] = str(name)
    official_genres = [
        {"id": int(gid), "name": by_id[gid]}
        for gid in sorted(by_id.keys())
    ]
    return by_id, official_genres


def _normalize_genres(
    raw_genres: list[dict[str, Any]] | None,
    by_id: dict[int, str],
) -> list[dict[str, Any]]:
    genres: list[dict[str, Any]] = []
    seen = set()
    for item in raw_genres or []:
        if isinstance(item, dict) is False:
            continue
        genre_id = _safe_int(item.get("id"))
        genre_name = item.get("name")
        if genre_id is None and genre_name:
            text = str(genre_name).strip().lower()
            for candidate_id, candidate_name in by_id.items():
                if str(candidate_name).strip().lower() == text:
                    genre_id = candidate_id
                    break
        if genre_id is None:
            continue
        genre_name = genre_name if str(genre_name).strip() else by_id.get(genre_id)
        if not genre_name:
            continue
        if genre_id in seen:
            continue
        seen.add(genre_id)
        genres.append({
            "id": int(genre_id),
            "name": str(genre_name),
        })
    genres.sort(key=lambda item: (str(item.get("name") or ""), int(item.get("id") or 0)))
    return genres


def _extract_genres(
    details: dict[str, Any] | None,
    search_item: dict[str, Any] | None,
    by_id: dict[int, str],
) -> list[dict[str, Any]]:
    raw_genres = None
    if isinstance(details, dict):
        raw_genres = details.get("genres")
        if not raw_genres and isinstance(details.get("genre_ids"), list):
            raw_genres = [{"id": value} for value in details.get("genre_ids")]
    if (not raw_genres or raw_genres == []) and isinstance(search_item, dict):
        raw_genres = search_item.get("genre_ids")
        if raw_genres and isinstance(raw_genres, list):
            raw_genres = [{"id": value} for value in raw_genres]
    if not raw_genres:
        return []
    normalized = _normalize_genres(raw_genres, by_id)
    return normalized


def _title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def _choose_search_match(
    results: list[dict[str, Any]],
    title: str,
    year: int | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if not results:
        return None, None
    target = _normalize_cache_title(title)
    candidates: list[tuple[int, float, int, float, str | None, dict[str, Any]]] = []
    for item in results:
        candidate_name = str((item.get("name") or item.get("original_name") or "")).strip()
        candidate_year = _extract_year(item.get("first_air_date"))
        candidate_norm = _normalize_cache_title(candidate_name)
        similarity = _title_similarity(target, candidate_norm)
        year_priority = 0
        warning = None
        if year is not None and candidate_year is not None:
            diff = abs(candidate_year - year)
            if diff == 0:
                year_priority = 2
            elif diff == 1:
                year_priority = 1
                warning = f"год отличается на 1: dataset={year}, tmdb={candidate_year}"
            else:
                warning = f"год отличается: dataset={year}, tmdb={candidate_year}"
        candidates.append((
            year_priority,
            similarity,
            _safe_int(item.get("vote_count")) or 0,
            item.get("popularity") or 0.0,
            warning,
            item,
        ))
    if not candidates:
        return None, None
    candidates.sort(key=lambda entry: entry[:4], reverse=True)
    match = candidates[0][5]
    warning = candidates[0][4]
    return match, warning


def _build_entry(
    title: str,
    year: int | None,
    *,
    status: str,
    tmdb_id: int | None,
    matched_title: str | None = None,
    matched_year: int | None = None,
    genres: list[dict[str, Any]] | None = None,
    match_warning: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "cache_key": _build_cache_key(title, year),
        "title": title,
        "year": year,
        "tmdb_id": tmdb_id,
        "matched_title": matched_title,
        "matched_year": matched_year,
        "genres": genres or [],
        "status": status,
        "match_warning": match_warning,
        "error": error,
    }


def _resolve_item(
    title: str,
    year: int | None,
    meta_obj: dict[str, Any],
    by_id: dict[int, str],
    *,
    language: str,
    refresh: bool,
) -> dict[str, Any]:
    tmdb_id = _extract_tmdb_id(meta_obj)
    normalized_title = title
    error = None
    match_warning = None
    matched_title = None
    matched_year = year

    if tmdb_id is not None:
        try:
            details = api_tmdb.get_tv_details(
                tmdb_id,
                language=language,
                force_refresh=refresh,
            )
            normalized = api_tmdb.normalize_tmdb_tv(details)
            matched_title = normalized.get("title") or normalized.get("original_title")
            matched_year = _safe_year(normalized.get("year"))
            genres = _extract_genres(details, None, by_id)
            status = STATUS_MATCHED if genres else STATUS_NO_GENRES
            return _build_entry(
                normalized_title,
                year,
                status=status,
                tmdb_id=tmdb_id,
                matched_title=matched_title,
                matched_year=matched_year,
                genres=genres,
            )
        except Exception as exception:
            error = str(exception)

    try:
        results = api_tmdb.search_tv_by_name(normalized_title, language=language)
        selected, warning = _choose_search_match(results, normalized_title, year)
        if selected is None:
            return _build_entry(
                normalized_title,
                year,
                status=STATUS_NOT_FOUND,
                tmdb_id=tmdb_id,
                match_warning=None,
                error=None,
            )

        selected_id = _safe_int(selected.get("id"))
        if selected_id is not None:
            tmdb_id = selected_id
            matched_title = str(selected.get("name") or "").strip() or None
            matched_year = _extract_year(selected.get("first_air_date"))
            match_warning = warning

            try:
                details = api_tmdb.get_tv_details(
                    tmdb_id,
                    language=language,
                    force_refresh=refresh,
                )
                genres = _extract_genres(details, selected, by_id)
                status = STATUS_MATCHED if genres else STATUS_NO_GENRES
                return _build_entry(
                    normalized_title,
                    year,
                    status=status,
                    tmdb_id=tmdb_id,
                    matched_title=matched_title,
                    matched_year=matched_year,
                    genres=genres,
                    match_warning=match_warning,
                )
            except Exception as exception:
                error = str(exception)
        return _build_entry(
            normalized_title,
            year,
            status=STATUS_NETWORK_ERROR,
            tmdb_id=tmdb_id,
            matched_title=matched_title,
            matched_year=matched_year,
            genres=[],
            match_warning=match_warning,
            error=error,
        )
    except Exception as exception:
        return _build_entry(
            normalized_title,
            year,
            status=STATUS_NETWORK_ERROR,
            tmdb_id=tmdb_id,
            match_warning=match_warning,
            error=str(exception),
        )


def _format_genre_line(genres: list[dict[str, Any]]) -> str:
    return ", ".join(f"{item.get('name')} ({item.get('id')})" for item in genres) or "-"


def _format_status(status: str | None) -> str:
    labels = {
        STATUS_MATCHED: "найдено",
        STATUS_NOT_FOUND: "не найдено",
        STATUS_NO_GENRES: "жанры не указаны",
        STATUS_NETWORK_ERROR: "ошибка сети",
        STATUS_SKIPPED_CACHED: "из кеша",
    }
    return labels.get(str(status or ""), str(status or "-"))


def _infer_cached_status(entry: dict[str, Any]) -> str:
    status = str(entry.get("status") or "")
    if status and status != STATUS_SKIPPED_CACHED:
        return status
    if entry.get("genres"):
        return STATUS_MATCHED
    if entry.get("error"):
        return STATUS_NETWORK_ERROR
    if entry.get("tmdb_id"):
        return STATUS_NO_GENRES
    return STATUS_NOT_FOUND


def _cache_storage_entry(entry: dict[str, Any]) -> dict[str, Any]:
    stored = dict(entry)
    stored.pop("from_cache", None)
    stored["status"] = _infer_cached_status(stored)
    return stored


def _write_txt_summary(report: dict[str, Any], output_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = output_dir / f"tmdb_genre_summary_{timestamp}.txt"
    lines: list[str] = [
        "Распределение жанров TMDb по dataset",
        f"Создано: {report.get('created_at')}",
        f"Всего записей в dataset: {report.get('dataset_items')}",
        f"Обработано: {report.get('processed')}",
        f"Найдено/распознано TMDb: {report.get('matched')}",
        f"Записей с жанрами: {report.get('items_with_genres')}",
        f"Взято из кеша: {report.get('from_cache')}",
        f"Не найдено: {report.get('not_found')}",
        f"Без жанров: {report.get('no_genres')}",
        f"Ошибки сети: {report.get('network_errors')}",
    ]
    if report.get("stopped_early"):
        lines.append(f"Остановлено досрочно: {report.get('stop_reason')}")
    if report.get("network_diagnostics"):
        lines.append("")
        lines.append("Диагностика сети:")
        for line in report.get("network_diagnostics") or []:
            lines.append(str(line))
    lines.append("")
    lines.append("Официальные TV-жанры TMDb:")
    lines.append("ID      Название")
    for genre in report.get("official_tv_genres") or []:
        if not isinstance(genre, dict):
            continue
        lines.append(f"{genre.get('id', '')!s:>6}  {genre.get('name')}")
    lines.append("")
    lines.append("Количество по жанрам:")
    for name, count in (report.get("genre_counts") or {}).items():
        lines.append(f"{name}: {count}")
    lines.append("")
    lines.append("Заметки по фильтрам:")
    lines.append("TMDb использует ID жанров.")
    lines.append("with_genres=18|80 означает Drama ИЛИ Crime.")
    lines.append("with_genres=18,80 означает Drama И Crime.")
    lines.append("without_genres=10766 означает исключить Soap.")
    lines.append("")
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
    return path


def _write_txt_by_title(report: dict[str, Any], output_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = output_dir / f"tmdb_genre_by_title_{timestamp}.txt"
    lines: list[str] = []
    for item in report.get("items") or []:
        title = item.get("title") or "-"
        year = item.get("year") if item.get("year") is not None else "-"
        lines.append(f"{title} ({year})")
        lines.append(f"Статус: {_format_status(item.get('status'))}")
        lines.append(f"Источник: {'кеш' if item.get('from_cache') else 'текущий прогон'}")
        lines.append(f"TMDb ID: {item.get('tmdb_id') or '-'}")
        lines.append(f"Название в TMDb: {item.get('matched_title') or '-'}")
        lines.append(f"Жанры: {_format_genre_line(item.get('genres') or [])}")
        if item.get("match_warning"):
            lines.append(f"Предупреждение по совпадению: {item.get('match_warning')}")
        if item.get("error"):
            lines.append(f"Ошибка: {item.get('error')}")
        lines.append("")
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
    return path


def _merge_cache_items(
    existing: dict[str, Any],
    processed_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    item_map: dict[str, dict[str, Any]] = {}
    existing_items = existing.get("items")
    if isinstance(existing_items, list):
        for entry in existing_items:
            if isinstance(entry, dict):
                key = str(entry.get("cache_key", ""))
                if key:
                    item_map[key] = _cache_storage_entry(entry)

    for entry in processed_items:
        key = str(entry.get("cache_key", ""))
        if key:
            item_map[key] = _cache_storage_entry(entry)

    all_items = list(item_map.values())
    genre_counts = Counter()
    for item in all_items:
        for genre in item.get("genres") or []:
            if isinstance(genre, dict):
                name = str(genre.get("name") or "").strip()
                if name:
                    genre_counts[name] += 1

    return all_items, dict(sorted(genre_counts.items(), key=lambda pair: (-pair[1], pair[0])))


def _genre_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for item in items:
        for genre in item.get("genres") or []:
            if isinstance(genre, dict):
                name = str(genre.get("name") or "").strip()
                if name:
                    counts[name] += 1

    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def _build_report(
    limit: int | None,
    *,
    refresh: bool,
    max_errors: int,
    language: str,
) -> dict[str, Any]:
    dataset = storage_data.load_dataset()
    meta = storage_data.load_meta()

    if len(dataset) == 0:
        raise RuntimeError("Dataset is empty.")

    existing_cache = _read_json(TMDB_GENRE_CACHE_PATH)
    fallback_official = existing_cache.get("official_tv_genres")
    if isinstance(fallback_official, list):
        fallback_map = {}
        for item in fallback_official:
            if isinstance(item, dict):
                fallback_id = _safe_int(item.get("id"))
                fallback_name = item.get("name")
                if fallback_id is not None and fallback_name:
                    fallback_map[fallback_id] = str(fallback_name)
    else:
        fallback_official = []
        fallback_map = {}

    try:
        official_map, official_tv_genres = _official_genre_map(language, force_refresh=refresh)
    except Exception:
        official_tv_genres = fallback_official
        official_map = fallback_map

    dataset_items = list(dataset.items())
    if limit is not None and limit > 0:
        dataset_items = dataset_items[:limit]

    stopped_early = False
    stop_reason = None
    consecutive_errors = 0
    processed_items: list[dict[str, Any]] = []
    cache_index = {
        str(item.get("cache_key")): item
        for item in existing_cache.get("items", [])
        if isinstance(item, dict) and item.get("cache_key")
    }

    for title, record in dataset_items:
        title_text, year = _extract_dataset_title_and_year(title, record)
        meta_obj = _find_meta_obj(meta, title_text) or {}
        cache_key = _build_cache_key(title_text, year)

        if refresh is False and cache_key in cache_index:
            cached_item = dict(cache_index[cache_key])
            cached_status = _infer_cached_status(cached_item)
            if cached_status not in RETRIABLE_CACHE_STATUSES:
                cached_item["status"] = cached_status
                cached_item["cache_key"] = cache_key
                cached_item["from_cache"] = True
                processed_items.append(cached_item)
                continue

        item = _resolve_item(
            title_text,
            year,
            meta_obj,
            official_map,
            language=language,
            refresh=refresh,
        )
        processed_items.append(item)
        cache_index[cache_key] = item

        if item.get("status") == STATUS_NETWORK_ERROR:
            consecutive_errors += 1
            if max_errors > 0 and consecutive_errors >= max_errors:
                stopped_early = True
                stop_reason = f"остановлено после {consecutive_errors} сетевых ошибок подряд: {item.get('error')}"
                break
        else:
            consecutive_errors = 0

    status_counter = Counter(item.get("status") for item in processed_items)
    from_cache_count = sum(1 for item in processed_items if item.get("from_cache"))
    items_with_genres = sum(1 for item in processed_items if item.get("genres"))
    recognized_items = max(
        status_counter.get(STATUS_MATCHED, 0) + status_counter.get(STATUS_NO_GENRES, 0),
        items_with_genres + status_counter.get(STATUS_NO_GENRES, 0),
    )
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": "dataset",
        "language": language,
        "refresh": refresh,
        "dataset_items": len(dataset),
        "processed": len(processed_items),
        "matched": recognized_items,
        "items_with_genres": items_with_genres,
        "from_cache": from_cache_count,
        "not_found": status_counter.get(STATUS_NOT_FOUND, 0),
        "no_genres": status_counter.get(STATUS_NO_GENRES, 0),
        "network_errors": status_counter.get(STATUS_NETWORK_ERROR, 0),
        "items": processed_items,
        "stopped_early": stopped_early,
        "stop_reason": stop_reason,
        "unmatched": status_counter.get(STATUS_NOT_FOUND, 0) + status_counter.get(STATUS_NETWORK_ERROR, 0),
        "network_diagnostics": (
            _tmdb_network_diagnostics()
            if status_counter.get(STATUS_NETWORK_ERROR, 0) > 0
            else []
        ),
    }

    all_items, cache_genre_counts = _merge_cache_items(existing_cache, processed_items)
    report["genre_counts"] = _genre_counts(processed_items)
    report["official_tv_genres"] = official_tv_genres

    cache_to_save = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "tmdb",
        "items": all_items,
        "genre_counts": cache_genre_counts,
        "official_tv_genres": official_tv_genres,
    }
    _write_json(TMDB_GENRE_CACHE_PATH, cache_to_save)

    return report


def _print_console_report(report: dict[str, Any], summary_path: Path, by_title_path: Path) -> None:
    print("Распределение жанров TMDb по dataset")
    print(f"Создано: {report.get('created_at')}")
    print(f"Всего записей в dataset: {report.get('dataset_items')}")
    print(f"Обработано: {report.get('processed')}")
    print(f"Найдено/распознано TMDb: {report.get('matched')}")
    print(f"Записей с жанрами: {report.get('items_with_genres')}")
    print(f"Взято из кеша: {report.get('from_cache')}")
    print(f"Не найдено: {report.get('not_found')}")
    print(f"Без жанров: {report.get('no_genres')}")
    print(f"Ошибки сети: {report.get('network_errors')}")
    if report.get("stopped_early"):
        print(f"Остановлено досрочно: {report.get('stop_reason')}")
    if report.get("network_diagnostics"):
        print("Диагностика сети:")
        for line in report.get("network_diagnostics") or []:
            print(f"- {line}")
    print("Количество по жанрам:")
    for name, count in report.get("genre_counts", {}).items():
        print(f"{name}: {count}")
    print(f"Сводный отчёт: {summary_path}")
    print(f"Отчёт по тайтлам: {by_title_path}")
    print(f"JSON-кеш: {TMDB_GENRE_CACHE_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Собрать отчёт по жанрам TMDb для тайтлов из dataset.")
    parser.add_argument("--limit", type=int, default=None, help="Ограничить количество записей dataset для обработки.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Обновить кеш TMDb и принудительно делать сетевые запросы для обработанных записей.",
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=5,
        help="Максимум сетевых ошибок подряд перед остановкой.",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        help="Язык ответа TMDb для названий/жанров. По умолчанию en.",
    )

    args = parser.parse_args()

    limit = args.limit if args.limit is not None and args.limit > 0 else None
    language = args.language.strip() or "en"
    if not language:
        raise SystemExit("Некорректное значение --language.")

    try:
        report = _build_report(
            limit=limit,
            refresh=bool(args.refresh),
            max_errors=max(0, args.max_errors),
            language=language,
        )
    except Exception as error:
        raise SystemExit(f"Не удалось собрать отчёт: {error}") from error

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = _write_txt_summary(report, REPORT_DIR)
    by_title_path = _write_txt_by_title(report, REPORT_DIR)
    _print_console_report(report, summary_path, by_title_path)


if __name__ == "__main__":
    main()
