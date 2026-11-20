"""Update watched record use-case."""

import sqlite3

from config import constant
from dataset.models.results import UpdateRecordResult
from dataset.models.user_rating import normalize_user_rating
from dataset.records.features import build_computed_scores
from dataset.records.validation import (
    normalize_update_sections,
    validate_main_info_patch,
    validate_normalized_update_values,
    validate_update_patch_structure,
)


def _update_desktop_score(dataset_key: str, value) -> UpdateRecordResult:
    from storage.sqlite.watched_write import update_watched_user_score

    score = normalize_user_rating(value)
    if score is None:
        return UpdateRecordResult(
            False, dataset_key, "Оценка должна быть целым числом от 1 до 3.", "invalid_patch", []
        )
    try:
        reason = update_watched_user_score(dataset_key, score)
    except (OSError, sqlite3.Error):
        return UpdateRecordResult(
            False, dataset_key, "Не удалось сохранить оценку. Попробуйте ещё раз.", "save_error", []
        )
    if reason == "not_found":
        return UpdateRecordResult(False, dataset_key, "Запись не найдена.", reason, [])
    if reason == "nothing_changed":
        return UpdateRecordResult(True, dataset_key, "Изменений нет.", reason, [])
    return UpdateRecordResult(True, dataset_key, "Запись обновлена.", reason, ["main_info.user_score"])


def update_dataset_record(title, patch_payload, source_name: str = "") -> UpdateRecordResult:
    """Updates safe fields of an existing dataset record without changing its key."""
    if source_name == "desktop_gui" and isinstance(patch_payload, dict) and set(patch_payload) == {"main_info"}:
        score_patch = patch_payload["main_info"]
        if isinstance(score_patch, dict) and set(score_patch) == {"user_score"}:
            return _update_desktop_score(title, score_patch["user_score"])

    from storage.sqlite.watched_write import patch_watched_record

    key = str(title).strip() if title is not None else ""
    try:
        result = patch_watched_record(
            key, lambda dataset_key, movie, meta: _prepare_patch(dataset_key, movie, meta, patch_payload)
        )
    except (OSError, sqlite3.Error):
        return UpdateRecordResult(
            False, key or None, "Не удалось сохранить изменения. Попробуйте ещё раз.", "save_error", []
        )
    return result if result is not None else UpdateRecordResult(
        False, key or None, "Ошибка обновления! Запись не найдена", "not_found", []
    )


_RAW_IDENTITY_FIELDS = {"tmdb_id", "tmdbId", "id", "source", "imdb_id"}


def _with_preserved_raw_identity(previous: dict, normalized: dict) -> dict:
    return {**{key: previous[key] for key in _RAW_IDENTITY_FIELDS if key in previous}, **normalized}


def _prepare_patch(dataset_title, current_movie, meta, patch_payload):
    """Return the result and only the new payload/meta values that should be written."""
    structure_error = validate_update_patch_structure(patch_payload, dataset_title=dataset_title)
    if structure_error is not None:
        return structure_error, None, None

    main_info = dict(current_movie.get("main_info", {}))
    raw_scores = dict(current_movie.get("raw_scores", {}))
    changed_fields = []

    main_patch = patch_payload.get("main_info")
    main_error = validate_main_info_patch(main_patch, dataset_title=dataset_title, main_info=main_info)
    if main_error is not None:
        return main_error, None, None

    if isinstance(main_patch, dict):
        for field in ("user_score", "year", "country"):
            if field in main_patch and main_info.get(field) != main_patch[field]:
                main_info[field] = main_patch[field]
                changed_fields.append(f"main_info.{field}")

    raw_patch = patch_payload.get("raw_scores")
    if raw_patch is not None:
        if not isinstance(raw_patch, dict):
            return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректные raw_scores", "invalid_patch", []), None, None
        for field, value in raw_patch.items():
            if field not in constant.RAW_SCORES:
                return UpdateRecordResult(
                    False, dataset_title, f"Ошибка обновления! Неподдерживаемое поле raw_scores: {field}",
                    "invalid_patch", [],
                ), None, None
            if raw_scores.get(field) != value:
                raw_scores[field] = value
                changed_fields.append(f"raw_scores.{field}")

    no_change = UpdateRecordResult(True, dataset_title, "Изменений нет.", "nothing_changed", [])
    if not changed_fields and raw_patch is None:
        return no_change, None, None

    normalized = normalize_update_sections(dataset_title=dataset_title, main_info=main_info, raw_scores=raw_scores)
    if isinstance(normalized, UpdateRecordResult):
        return normalized, None, None

    new_main, new_raw = normalized
    values_error = validate_normalized_update_values(
        dataset_title=dataset_title,
        new_main_info=new_main,
        new_raw_scores=new_raw,
    )
    if values_error is not None:
        return values_error, None, None

    # The selected key may include a collision suffix or typed ID. It is not
    # the displayed title, and unrelated payload/metadata fields are untouched.
    display_title = main_info.get("title", current_movie.get("title", dataset_title))
    new_main = {**main_info, **new_main, "title": display_title}
    updated_meta = None
    if raw_patch is not None:
        meta_main = meta.get("main_info") or {}
        meta_raw = meta.get("raw_scores") or {}
        updated_meta = {
            **meta,
            "main_info": {**(meta_main if isinstance(meta_main, dict) else {}), **new_main},
            "raw_scores": _with_preserved_raw_identity(meta_raw if isinstance(meta_raw, dict) else {}, new_raw),
        }
    if not changed_fields:
        return no_change, None, updated_meta

    updated_movie = {
        **current_movie,
        "main_info": new_main,
        "raw_scores": _with_preserved_raw_identity(raw_scores, new_raw) if raw_patch is not None else raw_scores,
        "computed_scores": build_computed_scores(new_raw, new_main),
    }
    result = UpdateRecordResult(True, dataset_title, "Запись обновлена.", "updated", changed_fields)
    return result, updated_movie, updated_meta
