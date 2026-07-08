"""SQLite-backed watched dataset and meta compatibility facade."""

from __future__ import annotations

from common import valid
from storage.normalize import normalize_main_info, normalize_raw_scores


def init_dataset():
    """Ensure the watched dataset table exists."""
    from storage.sqlite.migrations import apply_migrations

    apply_migrations()


def load_dataset() -> dict:
    """Load watched records from SQLite."""
    from storage.sqlite.watched_repository import load_dataset_dict

    return load_dataset_dict()


def save_dataset(data: dict):
    """Save watched records to SQLite."""
    from storage.sqlite.watched_repository import save_dataset_dict

    save_dataset_dict(data)


def clean_dataset():
    """Clear watched payloads from SQLite while preserving compatible meta."""
    save_dataset({})


def is_origin_title(new_title: str) -> bool:
    """Return True when no watched title matches `new_title`."""
    from storage.sqlite.watched_repository import is_origin_title as sqlite_is_origin_title

    return sqlite_is_origin_title(new_title)


def get_all_titles() -> list:
    """Return all watched dataset keys."""
    return list(load_dataset().keys())


def find_exact_title(title: str) -> str | None:
    """Return the stored dataset key for a case-insensitive title match."""
    from storage.sqlite.watched_repository import find_exact_title as sqlite_find_exact_title

    return sqlite_find_exact_title(title)


def init_meta():
    """Ensure the watched meta table storage exists."""
    from storage.sqlite.migrations import apply_migrations

    apply_migrations()


def load_meta() -> dict:
    """Load watched meta from SQLite."""
    from storage.sqlite.watched_repository import load_meta_dict

    return load_meta_dict()


def save_meta(meta: dict):
    """Save watched meta to SQLite."""
    from storage.sqlite.watched_repository import save_meta_dict

    save_meta_dict(meta)


def clean_meta():
    """Clear watched meta from SQLite while preserving compatible payloads."""
    save_meta({})


def add_movies_to_meta(main_info: dict, raw: dict, extra_meta: dict | None = None, *, meta_key: str | None = None) -> bool:
    """Add normalized raw-score metadata for a watched title."""
    title = str(main_info["title"]).strip()
    meta = load_meta()

    if valid.is_correct_title(title) is False:
        return False

    if valid.is_correct_score(str(main_info["user_score"])) is False:
        return False

    if valid.is_correct_year(str(main_info["year"])) is False:
        return False

    if valid.is_valid_raw_meta(raw) is False:
        return False

    meta_obj = {}
    meta_obj["main_info"] = normalize_main_info(main_info)
    meta_obj["raw_scores"] = normalize_raw_scores(raw)
    if isinstance(extra_meta, dict):
        for key, value in extra_meta.items():
            if key in {"main_info", "raw_scores"}:
                continue
            meta_obj[key] = value
    meta[meta_key or title] = meta_obj

    save_meta(meta)
    return True


def title_in_meta(title: str) -> bool:
    """Return True when watched meta contains `title`."""
    return get_meta_obj(title) is not None


def get_meta_obj(title: str) -> dict:
    """Return watched meta object for a case-insensitive title match."""
    from storage.sqlite.watched_repository import get_meta_obj as sqlite_get_meta_obj

    return sqlite_get_meta_obj(title)


def rename_movie_title(old_title: str, new_title: str) -> bool:
    """Rename a watched dataset key and matching meta key in one transaction."""
    from storage.sqlite.connection import connect
    from storage.sqlite.migrations import apply_migrations
    from storage.sqlite.watched_repository import (
        find_exact_title as sqlite_find_exact_title,
        is_origin_title as sqlite_is_origin_title,
        load_dataset_dict,
        load_meta_dict,
        save_dataset_dict,
        save_meta_dict,
    )

    conn = connect()
    try:
        apply_migrations(conn)
        with conn:
            old_exact = sqlite_find_exact_title(old_title, conn=conn)
            if old_exact is None:
                return False

            new_title = str(new_title).strip()
            if valid.is_correct_title(new_title) is False:
                return False

            if old_exact.strip().lower() != new_title.lower() and sqlite_is_origin_title(new_title, conn=conn) is False:
                return False

            dataset = load_dataset_dict(conn=conn)
            movie = dataset.pop(old_exact)
            movie["main_info"] = normalize_main_info({
                **movie["main_info"],
                "title": new_title,
            })
            dataset[new_title] = movie

            meta = load_meta_dict(conn=conn)
            old_meta_title = None
            for meta_title in meta.keys():
                if meta_title.strip().lower() == old_exact.strip().lower():
                    old_meta_title = meta_title
                    break

            if old_meta_title is not None:
                meta_obj = meta.pop(old_meta_title)
                meta_obj["main_info"] = normalize_main_info({
                    **meta_obj["main_info"],
                    "title": new_title,
                })
                meta[new_title] = meta_obj

            save_dataset_dict(dataset, conn=conn)
            save_meta_dict(meta, conn=conn)
            return True
    finally:
        conn.close()
