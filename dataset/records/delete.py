"""Delete watched record use-case."""

from __future__ import annotations

import os
import shutil
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dataset.models.media_type import MOVIE_MEDIA_TYPE_ALIASES, TV_MEDIA_TYPE_ALIASES, normalize_media_type
from dataset.models.results import DeleteRecordResult
from posters.cache import (
    DEFAULT_POSTER_CACHE_JSON,
    load_poster_cache,
    poster_identity_key,
)
from storage import data as storage_data
from storage.sqlite.backup import REQUIRED_BACKUP_TABLES
from storage.sqlite.connection import connect, get_db_path
from storage.sqlite.json_codec import loads_json
from storage.sqlite.migrations import apply_migrations
from storage.sqlite.watched_mapper import extract_watched_record
from storage.sqlite.watched_write import upsert_watched_row


def _movie_title_year(dataset_key: str, movie: dict) -> tuple[str, object]:
    main_info = movie.get("main_info") or {}
    title = str(main_info.get("title") or movie.get("title") or dataset_key).strip()
    year = main_info.get("year", movie.get("year"))
    return title, year


def search_watched_records_by_query(query: str, data: dict | None = None) -> list[dict]:
    """Return watched records whose title matches query (case-insensitive substring)."""
    dataset = data if data is not None else storage_data.load_dataset()
    normalized_query = str(query or "").strip().casefold()
    if normalized_query == "":
        return []

    matches: list[dict] = []
    for dataset_key, movie in dataset.items():
        if isinstance(movie, dict) is False:
            continue
        title, year = _movie_title_year(dataset_key, movie)
        haystack = f"{dataset_key} {title}".casefold()
        if normalized_query not in haystack:
            continue

        main_info = movie.get("main_info") or {}
        raw_scores = movie.get("raw_scores") or {}
        matches.append(
            {
                "dataset_key": dataset_key,
                "title": title,
                "year": year,
                "user_score": main_info.get("user_score"),
                "tmdb_score": raw_scores.get("tmdb_score"),
            }
        )

    matches.sort(key=lambda item: (str(item["title"]).casefold(), str(item.get("year") or "")))
    return matches


def build_watched_delete_preview(dataset_key: str, data: dict | None = None) -> dict | None:
    """Build read-only preview for one dataset record before deletion."""
    dataset = data if data is not None else storage_data.load_dataset()
    movie = dataset.get(dataset_key)
    if isinstance(movie, dict) is False:
        return None

    title, year = _movie_title_year(dataset_key, movie)
    main_info = movie.get("main_info") or {}
    raw_scores = movie.get("raw_scores") or {}
    meta = storage_data.load_meta()
    meta_key = dataset_key if isinstance(meta.get(dataset_key), dict) else None

    poster_cache = load_poster_cache()
    cache_identity = poster_identity_key(title, year)
    cache_entry = poster_cache.get(cache_identity)
    if isinstance(cache_entry, dict) is False:
        cache_entry = None

    local_path = None
    if isinstance(cache_entry, dict):
        local_path = cache_entry.get("local_path")

    return {
        "dataset_key": dataset_key,
        "title": title,
        "year": year,
        "user_score": main_info.get("user_score"),
        "tmdb_score": raw_scores.get("tmdb_score"),
        "tmdb_votes": raw_scores.get("tmdb_votes"),
        "has_meta": meta_key is not None,
        "meta_key": meta_key,
        "has_poster_cache": cache_entry is not None,
        "poster_cache_identity": cache_identity,
        "poster_local_path": local_path,
        "poster_status": cache_entry.get("status") if isinstance(cache_entry, dict) else None,
    }


def backup_before_watched_delete(timestamp: str | None = None) -> list[str]:
    """Backup SQLite runtime DB and poster-cache before delete."""
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f".backup_before_delete_{stamp}"
    backups: list[str] = []

    from storage.files import create_backup

    backup_path = create_backup()
    backups.append(str(backup_path))

    poster_cache_path = DEFAULT_POSTER_CACHE_JSON
    if poster_cache_path.is_file():
        destination = poster_cache_path.with_name(poster_cache_path.name + suffix)
        temp_destination = destination.with_name(destination.name + ".tmp")
        try:
            shutil.copy2(poster_cache_path, temp_destination)
            os.replace(temp_destination, destination)
        finally:
            try:
                temp_destination.unlink()
            except OSError:
                pass
        backups.append(str(destination))

    return backups


@dataclass(frozen=True)
class _SelectedRecord:
    payload_json: str
    meta_json: str | None
    created_at: str
    updated_at: str

    @property
    def movie(self) -> dict:
        obj = loads_json(self.payload_json, {})
        return obj if isinstance(obj, dict) else {}


def _selected_record(conn: sqlite3.Connection, dataset_key: str) -> _SelectedRecord | None:
    row = conn.execute(
        "SELECT payload_json, meta_json, created_at, updated_at FROM watched_records WHERE dataset_key = ?",
        (dataset_key,),
    ).fetchone()
    if row is None:
        return None
    selected = _SelectedRecord(*row)
    return selected if selected.movie else None


def _poster_payload(conn: sqlite3.Connection, identity: str) -> str | None:
    row = conn.execute(
        "SELECT payload_json FROM poster_cache_entries WHERE identity_key = ?", (identity,)
    ).fetchone()
    return None if row is None else row[0]


def _check_delete_backup(
    backups: list[str], dataset_key: str, selected: _SelectedRecord, identity: str
) -> str | None:
    if not backups:
        raise ValueError("Missing SQLite delete backup")
    backup = Path(backups[0]).resolve()
    if backup.samefile(get_db_path()):
        raise ValueError("Delete backup must not be the active database")
    # Read-only also prevents a missing backup path from creating an empty file.
    with closing(sqlite3.connect(f"{backup.as_uri()}?mode=ro", uri=True)) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if (
            not REQUIRED_BACKUP_TABLES <= tables
            or conn.execute("PRAGMA quick_check").fetchall() != [("ok",)]
            or conn.execute("PRAGMA foreign_key_check").fetchone() is not None
            or _selected_record(conn, dataset_key) != selected
        ):
            raise ValueError("SQLite delete backup is not a recoverable copy of the selected record")
        return _poster_payload(conn, identity)


def _watched_count(conn: sqlite3.Connection) -> int:
    return sum(
        isinstance(obj := loads_json(row[0], None), dict) and bool(obj)
        for row in conn.execute("SELECT payload_json FROM watched_records")
    )


def _identity_is_shared(conn: sqlite3.Connection, dataset_key: str | None, identity: str) -> bool:
    for row in conn.execute(
        "SELECT dataset_key, payload_json, meta_json FROM watched_records WHERE dataset_key IS NOT ?",
        (dataset_key,),
    ):
        # Poster keys do not contain trusted IDs. A sibling with the same
        # title/year may own this entry even if its typed ID is different.
        for raw in (row["payload_json"], row["meta_json"]):
            obj = loads_json(raw, None)
            if not isinstance(obj, dict) or not obj:
                continue
            title, year = _movie_title_year(row["dataset_key"], obj)
            if poster_identity_key(title, year) == identity:
                return True
    return False


def _cache_entry_for_remove(
    conn: sqlite3.Connection, dataset_key: str, identity: str, backed_up_payload: str | None
) -> dict | None:
    if (
        backed_up_payload is None
        or _poster_payload(conn, identity) != backed_up_payload
        or _identity_is_shared(conn, dataset_key, identity)
    ):
        return None
    obj = loads_json(backed_up_payload, None)
    return obj if isinstance(obj, dict) else None


def _delete_unshared_poster_file(conn: sqlite3.Connection, identity: str, cache_entry: dict) -> int:
    from posters.download_images import DEFAULT_POSTER_IMAGES_DIR, poster_image_path_for_identity

    # Keep paths still referenced by another cache entry. Failure to unlink an
    # image after the SQLite commit must not turn success into a failed delete.
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute(
                "SELECT 1 FROM poster_cache_entries WHERE identity_key = ?", (identity,)
            ).fetchone() or _identity_is_shared(conn, None, identity):
                return 0
            managed_root = DEFAULT_POSTER_IMAGES_DIR.absolute()
            if managed_root.resolve(strict=True) != managed_root:
                return 0
            paths = {poster_image_path_for_identity(identity)}
            if cache_entry.get("local_path"):
                paths.add(Path(str(cache_entry["local_path"])))
            retained = set()
            for row in conn.execute("SELECT identity_key, local_path FROM poster_cache_entries"):
                retained.add(poster_image_path_for_identity(row[0]).resolve())
                if row[1]:
                    retained.add(Path(row[1]).resolve())
            deleted = False
            for path in paths:
                candidate = path.absolute()
                try:
                    resolved = candidate.resolve(strict=True)
                    if (
                        not resolved.is_relative_to(managed_root)
                        or resolved != candidate
                        or resolved in retained
                        or not stat.S_ISREG(candidate.lstat().st_mode)
                    ):
                        continue
                    candidate.unlink()
                    deleted = True
                except (OSError, RuntimeError, ValueError):
                    continue
            return int(deleted)
    except (OSError, sqlite3.Error, ValueError, RuntimeError):
        return 0


def _metadata_belongs_elsewhere(dataset_key: str, movie: dict, meta: dict) -> bool:
    # Imported profiles can put unrelated metadata under the selected key.
    # Exact key owns the meta by default; preserve when IDs positively disagree.
    watched = extract_watched_record(dataset_key, movie)
    metadata = extract_watched_record(dataset_key, {}, meta=meta)
    if watched.tmdb_id and metadata.tmdb_id:
        if watched.tmdb_id != metadata.tmdb_id:
            return True
        media_types = []
        for payload in (movie, meta):
            main = payload.get("main_info")
            value = main.get("media_type") if isinstance(main, dict) else None
            text = str(value or payload.get("media_type") or "").strip().casefold()
            if text not in MOVIE_MEDIA_TYPE_ALIASES | TV_MEDIA_TYPE_ALIASES:
                break
            media_types.append(normalize_media_type(text))
        if len(media_types) == 2 and media_types[0] != media_types[1]:
            return True
    return bool(watched.imdb_id and metadata.imdb_id and watched.imdb_id != metadata.imdb_id)


def delete_watched_record(dataset_key: str, *, timestamp: str | None = None) -> DeleteRecordResult:
    """Delete exactly the selected watched row and its unshared cache after backup."""
    backups: list[str] = []
    dataset_count = 0
    try:
        with closing(connect()) as conn:
            apply_migrations(conn)
            selected = _selected_record(conn, dataset_key)
            dataset_count = _watched_count(conn)
            if selected is None:
                return DeleteRecordResult(
                    ok=False, dataset_key=dataset_key, message="Запись не найдена в dataset.",
                    reason="not_found", dataset_count=dataset_count, backups=[],
                )

            title, year = _movie_title_year(dataset_key, selected.movie)
            identity = poster_identity_key(title, year)
            try:
                backups = backup_before_watched_delete(timestamp=timestamp)
                backed_up_poster = _check_delete_backup(backups, dataset_key, selected, identity)
            except (OSError, sqlite3.Error, ValueError):
                return DeleteRecordResult(
                    ok=False, dataset_key=dataset_key,
                    message="Не удалось проверить резервную копию. Удаление отменено.",
                    reason="backup_error", dataset_count=dataset_count, backups=[],
                )

            with conn:
                conn.execute("BEGIN IMMEDIATE")
                if _selected_record(conn, dataset_key) != selected:
                    return DeleteRecordResult(
                        ok=False, dataset_key=dataset_key,
                        message="Запись изменилась. Откройте коллекцию заново и повторите удаление.",
                        reason="record_changed", dataset_count=_watched_count(conn), backups=backups,
                    )
                meta = loads_json(selected.meta_json, None)
                preserve_meta = isinstance(meta, dict) and _metadata_belongs_elsewhere(
                    dataset_key, selected.movie, meta
                )
                cache_entry = None if preserve_meta else _cache_entry_for_remove(
                    conn, dataset_key, identity, backed_up_poster
                )
                if preserve_meta:
                    upsert_watched_row(
                        conn, dataset_key=dataset_key, payload={}, meta=meta, created_at=selected.created_at
                    )
                else:
                    conn.execute("DELETE FROM watched_records WHERE dataset_key = ?", (dataset_key,))
                if cache_entry is not None:
                    conn.execute("DELETE FROM poster_cache_entries WHERE identity_key = ?", (identity,))
                dataset_count = _watched_count(conn)

            deleted_poster_file = (
                _delete_unshared_poster_file(conn, identity, cache_entry) if cache_entry is not None else 0
            )
    except (OSError, sqlite3.Error):
        return DeleteRecordResult(
            ok=False, dataset_key=dataset_key,
            message="Не удалось сохранить изменения. Запись не удалена.",
            reason="save_error", dataset_count=dataset_count, backups=backups,
        )

    return DeleteRecordResult(
        ok=True, dataset_key=dataset_key, message="Запись удалена.", reason="deleted",
        title=title, year=year, deleted_dataset=1, deleted_meta=int(selected.meta_json is not None and not preserve_meta),
        deleted_poster_cache=int(cache_entry is not None), deleted_poster_file=deleted_poster_file,
        dataset_count=dataset_count, backups=backups,
    )
