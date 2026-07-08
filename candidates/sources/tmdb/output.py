"""TMDb build result output, CSV export, and genre distribution reports."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from apis import tmdb_api as api_tmdb
from dataset.models.media_type import MEDIA_TYPE_MOVIE, normalize_media_type


ROOT_DIR = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT_DIR / "data" / "exports" / "candidate_pool"
DIAGNOSTICS_DIR = ROOT_DIR / "data" / "diagnostics"

CSV_FIELDS = [
    "final_score",
    "country_score",
    "quality_score",
    "hidden_gem_score",
    "metadata_completeness_score",
    "media_type",
    "title",
    "original_title",
    "year",
    "release_date",
    "runtime",
    "tmdb_score",
    "tmdb_votes",
    "tmdb_popularity",
    "is_complete",
    "missing_fields",
    "genres",
    "genre_keys",
    "countries",
    "country_codes",
    "original_language",
    "networks",
    "production_companies",
    "imdb_id",
    "tmdb_id",
    "country_signals",
    "overview",
    "description",
]


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def ensure_diagnostics_dir(output_dir: str | Path | None = None) -> Path:
    path = Path(output_dir) if output_dir is not None else DIAGNOSTICS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def unique_non_empty(values) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _genre_values_from_field(value) -> list[str]:
    result: list[str] = []
    for item in value or []:
        if isinstance(item, dict):
            text = str(item.get("name") or item.get("label") or "").strip()
        else:
            text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def output_base_path(country: str, mode: str, media_type: str | None = None) -> Path:
    ensure_output_dir()
    media_suffix = "_movie" if normalize_media_type(media_type) == MEDIA_TYPE_MOVIE else ""
    return OUTPUT_DIR / f"candidate_pool_{country.upper()}_{mode}{media_suffix}"


def _write_build_json(result: dict[str, Any], json_path: Path) -> Path | None:
    """Writes build JSON."""
    payload = dict(result)
    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return None


def save_candidate_pool_result(result: dict[str, Any]) -> tuple[Path, Path]:
    country = result["country"]
    mode = result["mode"]
    base_path = output_base_path(country, mode, media_type=result.get("media_type"))
    json_path = base_path.with_suffix(".json")
    csv_path = base_path.with_suffix(".csv")

    _write_build_json(result, json_path)

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in result["candidates"]:
            writer.writerow(candidate_to_csv_row(candidate))

    return json_path, csv_path


def save_candidate_pool_test_result(result: dict[str, Any]) -> tuple[Path, Path]:
    country = result["country"]
    mode = result["mode"]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ensure_output_dir()
    media_suffix = "_movie" if normalize_media_type(result.get("media_type")) == MEDIA_TYPE_MOVIE else ""
    base_path = OUTPUT_DIR / f"test_candidate_pool_{country.upper()}_{mode}{media_suffix}_{timestamp}"
    json_path = base_path.with_suffix(".json")
    csv_path = base_path.with_suffix(".csv")

    _write_build_json(result, json_path)

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in result["candidates"]:
            writer.writerow(candidate_to_csv_row(candidate))

    return json_path, csv_path


def list_tmdb_result_files() -> list[Path]:
    ensure_output_dir()
    files = [
        path for path in OUTPUT_DIR.glob("*candidate_pool_*.json")
        if path.is_file()
    ]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files


def normalize_tmdb_candidate_for_common_import(candidate: dict[str, Any], criteria_name: str) -> dict[str, Any]:
    from candidates.sources.tmdb import importer as import_tmdb

    return import_tmdb.normalize_tmdb_candidate_for_common_import(candidate, criteria_name)


def tmdb_import_default_criteria_name(result: dict[str, Any]) -> str | None:
    from candidates.sources.tmdb import importer as import_tmdb

    return import_tmdb.tmdb_import_default_criteria_name(result)


def import_tmdb_result_to_common_pool(result_path, criteria_name: str | None = None) -> dict[str, Any]:
    from candidates.sources.tmdb import importer as import_tmdb

    return import_tmdb.import_tmdb_result_to_common_pool(result_path, criteria_name=criteria_name)


def _safe_year(value) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _find_nested_value(data, key: str):
    if isinstance(data, dict) is False:
        return None
    if key in data and data[key] not in (None, ""):
        return data[key]
    for value in data.values():
        if isinstance(value, dict):
            found = _find_nested_value(value, key)
            if found not in (None, ""):
                return found
        elif isinstance(value, list):
            for item in value:
                found = _find_nested_value(item, key)
                if found not in (None, ""):
                    return found
    return None


def _tmdb_id_from_meta(meta_obj: dict | None):
    if isinstance(meta_obj, dict) is False:
        return None
    return (
        meta_obj.get("tmdb_id")
        or _find_nested_value(meta_obj.get("tmdb_data"), "tmdb_id")
        or _find_nested_value(meta_obj.get("tmdb_data"), "id")
        or _find_nested_value(meta_obj.get("source_values"), "tmdb_id")
    )


def _genres_from_tmdb_details(details: dict[str, Any]) -> list[str]:
    if isinstance(details, dict) is False:
        return []
    if "genres_tmdb" in details:
        return unique_non_empty(_genre_values_from_field(details.get("genres_tmdb")))
    return unique_non_empty(api_tmdb.normalize_tmdb_tv(details).get("genres_tmdb") or [])


def build_tmdb_genre_distribution_report(
    dataset: dict,
    meta: dict | None = None,
    *,
    details_fetcher=None,
    search_func=None,
    choose_func=None,
    normalizer=None,
    progress_callback=None,
    max_consecutive_errors: int | None = 3,
) -> dict[str, Any]:
    details_fetcher = details_fetcher or api_tmdb.get_tv_details
    search_func = search_func or api_tmdb.search_tv_by_name
    choose_func = choose_func or api_tmdb.choose_best_result
    normalizer = normalizer or api_tmdb.normalize_tmdb_tv
    meta = meta or {}

    created_at = datetime.now().isoformat(timespec="seconds")
    genre_counts: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    unmatched_items: list[dict[str, Any]] = []
    empty_genre_items: list[dict[str, Any]] = []
    consecutive_errors = 0
    stopped_early = False
    stop_reason = None

    dataset_items = list((dataset or {}).items())
    total_items = len(dataset_items)
    for index, (title, record) in enumerate(dataset_items, start=1):
        main_info = record.get("main_info") if isinstance(record, dict) else {}
        title_text = str((main_info or {}).get("title") or title or "").strip()
        year = _safe_year((main_info or {}).get("year"))
        meta_obj = meta.get(title) or meta.get(title_text) or {}
        tmdb_id = _tmdb_id_from_meta(meta_obj)
        matched = False
        genres: list[str] = []
        error = None
        if progress_callback is not None:
            progress_callback({
                "index": index,
                "total": total_items,
                "title": title_text,
                "year": year,
                "status": "start",
                "tmdb_id": safe_int(tmdb_id),
                "genres": [],
            })

        try:
            if tmdb_id in (None, ""):
                results = search_func(title_text)
                selected = choose_func(results)
                if selected:
                    tmdb_id = selected.get("id")

            if tmdb_id not in (None, ""):
                details = details_fetcher(int(tmdb_id))
                normalized_details = normalizer(details)
                genres = unique_non_empty(
                    normalized_details.get("genres_tmdb")
                    or _genres_from_tmdb_details(details)
                )
                matched = True
        except Exception as exc:
            error = str(exc)
            matched = False

        item = {
            "title": title_text,
            "year": year,
            "tmdb_id": safe_int(tmdb_id),
            "matched": matched,
            "genres": genres,
        }
        if error:
            item["error"] = error
        items.append(item)

        if matched:
            consecutive_errors = 0
            if len(genres) == 0:
                empty_genre_items.append({"title": title_text, "year": year, "tmdb_id": safe_int(tmdb_id)})
            for genre_name in genres:
                genre_counts[genre_name] = genre_counts.get(genre_name, 0) + 1
        else:
            unmatched_items.append({"title": title_text, "year": year})
            if error:
                consecutive_errors += 1
            else:
                consecutive_errors = 0

        if progress_callback is not None:
            status = "matched" if matched else "unmatched"
            if error:
                status = "error"
            progress_callback({
                "index": index,
                "total": total_items,
                "title": title_text,
                "year": year,
                "status": status,
                "tmdb_id": safe_int(tmdb_id),
                "genres": genres,
                "error": error,
            })

        if (
            max_consecutive_errors is not None
            and max_consecutive_errors > 0
            and consecutive_errors >= max_consecutive_errors
        ):
            stopped_early = True
            stop_reason = f"Остановлено после {consecutive_errors} подряд ошибок TMDb: {error}"
            if progress_callback is not None:
                progress_callback({
                    "index": index,
                    "total": total_items,
                    "title": title_text,
                    "year": year,
                    "status": "stopped",
                    "error": stop_reason,
                    "processed": len(items),
                })
            break

    genre_counts = dict(sorted(genre_counts.items(), key=lambda pair: (-pair[1], pair[0])))
    return {
        "created_at": created_at,
        "source": "dataset",
        "total_dataset_items": len(dataset or {}),
        "matched": sum(1 for item in items if item["matched"]),
        "unmatched": len(unmatched_items),
        "processed": len(items),
        "stopped_early": stopped_early,
        "stop_reason": stop_reason,
        "genre_counts": genre_counts,
        "items": items,
        "unmatched_items": unmatched_items,
        "empty_genre_items": empty_genre_items,
    }


def save_tmdb_genre_distribution_report(report: dict[str, Any], output_dir: str | Path | None = None) -> Path:
    diagnostics_dir = ensure_diagnostics_dir(output_dir)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = diagnostics_dir / f"tmdb_genre_distribution_{timestamp}.json"
    with open(path, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return path


def candidate_to_csv_row(candidate: dict[str, Any]) -> dict[str, Any]:
    row = {}
    for field in CSV_FIELDS:
        value = candidate.get(field)
        if field == "production_countries":
            value = candidate.get("tmdb_production_countries")
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        row[field] = value
    return row


def build_summary_lines(result: dict[str, Any]) -> list[str]:
    """Возвращает строки итогового отчёта (печать выполняет UI/CLI)."""
    stats = result["stats"]
    lines = [
        f"Источник: {stats.get('source', 'tmdb')} v{stats.get('source_version', 2)}",
        f"Найдено через TMDb Discover: {stats['discover_total']}",
        f"Удалено дублей: {stats['duplicates_removed']}",
        f"Пропущено уже просмотренных: {stats['watched_skipped']}",
        f"Пропущено уже в pool по TMDb ID: {stats.get('existing_pool_skipped_tmdb_id', 0)}",
        f"Пропущено уже в pool по title/year: {stats.get('existing_pool_skipped_title_year', 0)}",
        f"Запрошено TMDb Details: {stats['details_requested']}",
        f"TMDb Details ошибок сети: {stats.get('details_errors', 0)}",
        f"С IMDb ID из TMDb external_ids: {stats.get('external_ids_imdb_id_count', 0)}",
        f"Complete кандидатов: {stats['complete_candidates']}",
        f"С неполной TMDb/core metadata: {stats.get('incomplete_candidates', 0)}",
        f"Итоговых кандидатов: {stats['final_candidates']}",
        "",
        "Топ-20 по final_score",
        "-" * 80,
    ]
    for index, candidate in enumerate(result["candidates"][:20], start=1):
        lines.append(
            f"{index:>2}. {candidate.get('final_score'):.3f} | "
            f"{candidate.get('title') or '-'} ({candidate.get('year') or '-'}) | "
            f"TMDb {candidate.get('tmdb_score') or '-'} / {candidate.get('tmdb_votes') or 0}"
        )
    return lines
