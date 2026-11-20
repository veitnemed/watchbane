"""Update watched record use-case."""

import sqlite3

from config import constant
from dataset.meta.sync import sync_raw_scores_to_meta
from dataset.models.identity import find_dataset_title
from dataset.models.results import UpdateRecordResult
from dataset.models.user_rating import normalize_user_rating
from dataset.records.features import build_computed_scores
from dataset.records.validation import (
    normalize_update_sections,
    validate_main_info_patch,
    validate_normalized_update_values,
    validate_update_patch_structure,
)
from storage.data import load_dataset, save_dataset
from storage.normalize import normalize_main_info, normalize_raw_scores


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

    data = load_dataset()
    dataset_title = find_dataset_title(data, title)
    if dataset_title is None:
        return UpdateRecordResult(
            ok=False,
            title=str(title).strip() if title is not None else None,
            message="Ошибка обновления! Запись не найдена",
            reason="not_found",
            changed_fields=[],
        )

    structure_error = validate_update_patch_structure(patch_payload, dataset_title=dataset_title)
    if structure_error is not None:
        return structure_error

    current_movie = data[dataset_title]
    main_info = dict(current_movie.get("main_info", {}))
    raw_scores = dict(current_movie.get("raw_scores", {}))
    changed_fields = []

    main_patch = patch_payload.get("main_info")
    main_error = validate_main_info_patch(
        main_patch,
        dataset_title=dataset_title,
        main_info=main_info,
    )
    if main_error is not None:
        return main_error

    if isinstance(main_patch, dict):
        for field in ("user_score", "year", "country"):
            if field in main_patch and main_info.get(field) != main_patch[field]:
                main_info[field] = main_patch[field]
                changed_fields.append(f"main_info.{field}")

    raw_patch = patch_payload.get("raw_scores")
    if raw_patch is not None:
        if isinstance(raw_patch, dict) is False:
            return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректные raw_scores", "invalid_patch", [])
        for field, value in raw_patch.items():
            if field not in constant.RAW_SCORES:
                return UpdateRecordResult(
                    ok=False,
                    title=dataset_title,
                    message=f"Ошибка обновления! Неподдерживаемое поле raw_scores: {field}",
                    reason="invalid_patch",
                    changed_fields=[],
                )
            if raw_scores.get(field) != value:
                raw_scores[field] = value
                changed_fields.append(f"raw_scores.{field}")

    if len(changed_fields) == 0:
        if raw_patch is not None:
            try:
                current_main_info = normalize_main_info({**main_info, "title": dataset_title})
                current_raw_scores = normalize_raw_scores(raw_scores)
                sync_raw_scores_to_meta(dataset_title, current_main_info, current_raw_scores)
            except Exception as error:
                return UpdateRecordResult(
                    ok=False,
                    title=dataset_title,
                    message=f"Ошибка обновления! Не удалось синхронизировать meta: {error}",
                    reason="save_error",
                    changed_fields=[],
                )
        return UpdateRecordResult(
            ok=True,
            title=dataset_title,
            message="Изменений нет.",
            reason="nothing_changed",
            changed_fields=[],
        )

    normalized = normalize_update_sections(
        dataset_title=dataset_title,
        main_info=main_info,
        raw_scores=raw_scores,
    )
    if isinstance(normalized, UpdateRecordResult):
        return normalized

    new_main_info, new_raw_scores = normalized

    values_error = validate_normalized_update_values(
        dataset_title=dataset_title,
        new_main_info=new_main_info,
        new_raw_scores=new_raw_scores,
    )
    if values_error is not None:
        return values_error

    computed_scores = build_computed_scores(new_raw_scores, new_main_info)

    updated_movie = {
        "main_info": new_main_info,
        "raw_scores": new_raw_scores,
        "computed_scores": computed_scores,
    }
    for field_name in ("localized", "genres_tmdb"):
        if field_name in current_movie:
            updated_movie[field_name] = current_movie[field_name]
    data[dataset_title] = updated_movie

    try:
        save_dataset(data)
        if raw_patch is not None:
            sync_raw_scores_to_meta(dataset_title, new_main_info, new_raw_scores)
    except Exception as error:
        return UpdateRecordResult(
            ok=False,
            title=dataset_title,
            message=f"Ошибка обновления! Не удалось сохранить dataset: {error}",
            reason="save_error",
            changed_fields=[],
        )

    return UpdateRecordResult(
        ok=True,
        title=dataset_title,
        message="Запись обновлена.",
        reason="updated",
        changed_fields=changed_fields,
    )
