"""Add watched record use-case."""

from copy import deepcopy

from config import constant
from common import valid
from dataset.meta.merge import extract_extra_meta
from dataset.models.identity import build_dataset_record_key
from dataset.models.results import AddRecordResult
from dataset.records.features import build_computed_scores, build_feature_vector
from dataset.records.side_effects import run_after_add_side_effects
from dataset.records.validation import (
    ParsedAddPayload,
    validate_add_features,
    validate_add_record_payload,
)
from storage.data import add_movies_to_meta, get_meta_obj, load_dataset, load_meta, save_dataset, save_meta
from storage.normalize import normalize_main_info, normalize_raw_scores


def add_dataset_record(
    record_payload: dict,
    meta_payload=None,
    source_name: str = "",
    pool_candidate=None,
    poster_hints=None,
) -> AddRecordResult:
    """Adds a new record to dataset using the current add_movie behavior."""
    data = load_dataset()
    validated = validate_add_record_payload(record_payload, data=data)
    if isinstance(validated, AddRecordResult):
        return validated

    parsed: ParsedAddPayload = validated
    title = parsed.title
    main_info = parsed.main_info
    input_raw_scores = parsed.input_raw_scores
    tags_vibe = parsed.tags_vibe
    genre_tags = parsed.genre_tags
    year = parsed.year
    media_type = parsed.media_type
    dataset_key = build_dataset_record_key(data, title, year=year, media_type=media_type)

    extra_meta = extract_extra_meta(meta_payload)
    meta_obj = None
    if isinstance(meta_payload, dict) and (
        "raw_scores" in meta_payload or "raw" in meta_payload
    ):
        meta_obj = meta_payload
    else:
        meta_obj = get_meta_obj(dataset_key if dataset_key != title else title)
    if meta_obj is None:
        if valid.is_valid_raw_meta(input_raw_scores) is False:
            return AddRecordResult(
                ok=False,
                title=title,
                message="Ошибка добавления! Некорректные raw_scores",
                reason="invalid_payload",
            )

        raw_scores = normalize_raw_scores(input_raw_scores)
        meta_kwargs = {"meta_key": dataset_key} if dataset_key != title else {}
        if add_movies_to_meta(main_info, raw_scores, extra_meta=extra_meta, **meta_kwargs) is False:
            return AddRecordResult(
                ok=False,
                title=title,
                message="Ошибка добавления! Некорректные meta-данные",
                reason="invalid_payload",
            )
    else:
        raw_scores = meta_obj.get("raw_scores", meta_obj.get("raw"))
        if get_meta_obj(title) is None:
            normalized_meta_raw = normalize_raw_scores(raw_scores)
            if add_movies_to_meta(main_info, normalized_meta_raw, extra_meta=extra_meta) is False:
                return AddRecordResult(
                    ok=False,
                    title=title,
                    message="Ошибка добавления! Некорректные meta-данные",
                    reason="invalid_payload",
                )
        if extra_meta:
            stored_meta = load_meta()
            for meta_title, current_meta in stored_meta.items():
                if meta_title.strip().lower() != title.lower():
                    continue
                merged_meta = dict(current_meta)
                merged_meta.update(extra_meta)
                stored_meta[meta_title] = merged_meta
                save_meta(stored_meta)
                break

    raw_scores = normalize_raw_scores(raw_scores)
    new_main_info = normalize_main_info(main_info)
    computed_scores = build_computed_scores(raw_scores, new_main_info)
    features = build_feature_vector(computed_scores, tags_vibe, genre_tags)

    feature_error = validate_add_features(features, title=title)
    if feature_error is not None:
        return feature_error

    new_movie = {
        "main_info": new_main_info,
        "raw_scores": raw_scores,
        "computed_scores": computed_scores,
        constant.TAGS_VIBE_SECTION: tags_vibe,
        constant.GENRE_SECTION: genre_tags,
    }
    localized = record_payload.get("localized")
    if isinstance(localized, dict):
        new_movie["localized"] = deepcopy(localized)

    data[dataset_key] = new_movie
    try:
        save_dataset(data)
    except Exception as error:
        return AddRecordResult(
            ok=False,
            title=title,
            message=f"Ошибка добавления! Не удалось сохранить dataset: {error}",
            reason="save_error",
        )

    side_effects = run_after_add_side_effects(
        title=title,
        year=year,
        movie=new_movie,
        meta_obj=meta_obj,
        pool_candidate=pool_candidate,
        poster_hints=poster_hints,
    )
    return AddRecordResult(
        ok=True,
        title=dataset_key,
        message="Новая запись добавлена!",
        reason="saved",
        side_effects=side_effects,
    )
