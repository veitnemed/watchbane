"""Add watched record use-case."""

from copy import deepcopy

from common import valid
from dataset.meta.merge import extract_extra_meta
from dataset.models.identity import build_dataset_record_key, find_case_insensitive_key
from dataset.models.results import AddRecordResult
from dataset.records.features import build_computed_scores
from dataset.records.side_effects import run_after_add_side_effects
from dataset.records.validation import ParsedAddPayload, validate_add_record_payload
from storage.data import load_dataset, load_meta, save_dataset_and_meta
from storage.normalize import normalize_main_info, normalize_raw_scores


def _tmdb_id_from_meta(meta_obj: dict | None) -> int | None:
    if not isinstance(meta_obj, dict):
        return None
    raw_scores = meta_obj.get("raw_scores")
    values = (
        meta_obj.get("tmdb_id"),
        raw_scores.get("tmdb_id") if isinstance(raw_scores, dict) else None,
    )
    for value in values:
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _find_tmdb_duplicate(
    data: dict,
    meta: dict,
    *,
    tmdb_id: int | None,
    media_type: str,
) -> str | None:
    if tmdb_id is None:
        return None
    for dataset_key, record in data.items():
        main_info = record.get("main_info") if isinstance(record, dict) else None
        existing_media_type = normalize_main_info(main_info or {}).get("media_type")
        if existing_media_type != media_type:
            continue
        if _tmdb_id_from_meta(meta.get(dataset_key)) == tmdb_id:
            return str(dataset_key)
    return None


def _build_meta_obj(main_info: dict, raw: dict, extra_meta: dict | None = None) -> dict | None:
    title = str(main_info["title"]).strip()

    if valid.is_correct_title(title) is False:
        return None
    if valid.is_correct_score(str(main_info["user_score"])) is False:
        return None
    if valid.is_correct_year(str(main_info["year"])) is False:
        return None
    if valid.is_valid_raw_meta(raw) is False:
        return None

    meta_obj = {
        "main_info": normalize_main_info(main_info),
        "raw_scores": normalize_raw_scores(raw),
    }
    if isinstance(extra_meta, dict):
        for key, value in extra_meta.items():
            if key in {"main_info", "raw_scores"}:
                continue
            meta_obj[key] = value
    return meta_obj


def add_dataset_record(
    record_payload: dict,
    meta_payload=None,
    source_name: str = "",
    pool_candidate=None,
    poster_hints=None,
) -> AddRecordResult:
    """Adds a new record to dataset using the current add_movie behavior."""
    data = load_dataset()
    meta = load_meta()
    validated = validate_add_record_payload(record_payload, data=data)
    if isinstance(validated, AddRecordResult):
        return validated

    parsed: ParsedAddPayload = validated
    title = parsed.title
    main_info = parsed.main_info
    input_raw_scores = parsed.input_raw_scores
    year = parsed.year
    media_type = parsed.media_type
    duplicate_key = _find_tmdb_duplicate(
        data,
        meta,
        tmdb_id=_tmdb_id_from_meta(meta_payload),
        media_type=media_type,
    )
    if duplicate_key is not None:
        return AddRecordResult(
            ok=False,
            title=duplicate_key,
            message="This TMDb title is already in the watched collection.",
            reason="duplicate_tmdb_identity",
        )
    dataset_key = build_dataset_record_key(data, title, year=year, media_type=media_type)

    extra_meta = extract_extra_meta(meta_payload)
    existing_meta_key = find_case_insensitive_key(meta, dataset_key)
    if existing_meta_key is None and dataset_key == title:
        existing_meta_key = find_case_insensitive_key(meta, title)

    existing_meta_obj = meta.get(existing_meta_key) if existing_meta_key is not None else None
    if isinstance(meta_payload, dict) and (
        "raw_scores" in meta_payload or "raw" in meta_payload
    ):
        candidate_meta_obj = meta_payload
    else:
        candidate_meta_obj = existing_meta_obj

    if candidate_meta_obj is None:
        if valid.is_valid_raw_meta(input_raw_scores) is False:
            return AddRecordResult(
                ok=False,
                title=title,
                message="Ошибка добавления! Некорректные raw_scores",
                reason="invalid_payload",
            )

        raw_scores = normalize_raw_scores(input_raw_scores)
        new_meta_obj = _build_meta_obj(main_info, raw_scores, extra_meta=extra_meta)
        if new_meta_obj is None:
            return AddRecordResult(
                ok=False,
                title=title,
                message="Ошибка добавления! Некорректные meta-данные",
                reason="invalid_payload",
            )
        meta[dataset_key] = new_meta_obj
    else:
        raw_scores = candidate_meta_obj.get("raw_scores", candidate_meta_obj.get("raw"))
        target_meta_key = existing_meta_key or dataset_key
        if existing_meta_key is None:
            new_meta_obj = _build_meta_obj(main_info, normalize_raw_scores(raw_scores), extra_meta=extra_meta)
            if new_meta_obj is None:
                return AddRecordResult(
                    ok=False,
                    title=title,
                    message="Ошибка добавления! Некорректные meta-данные",
                    reason="invalid_payload",
                )
            meta[target_meta_key] = new_meta_obj
        if extra_meta:
            current_meta = meta.get(target_meta_key)
            if isinstance(current_meta, dict):
                merged_meta = dict(current_meta)
                merged_meta.update(extra_meta)
                meta[target_meta_key] = merged_meta

    raw_scores = normalize_raw_scores(raw_scores)
    new_main_info = normalize_main_info(main_info)
    computed_scores = build_computed_scores(raw_scores, new_main_info)

    new_movie = {
        "main_info": new_main_info,
        "raw_scores": raw_scores,
        "computed_scores": computed_scores,
    }
    localized = record_payload.get("localized")
    if isinstance(localized, dict):
        new_movie["localized"] = deepcopy(localized)
    genres_tmdb = record_payload.get("genres_tmdb")
    if isinstance(genres_tmdb, list) and genres_tmdb:
        new_movie["genres_tmdb"] = list(genres_tmdb)

    data[dataset_key] = new_movie
    try:
        if isinstance(pool_candidate, dict):
            from candidates.title_state_service import save_watched_dataset_transition

            save_watched_dataset_transition(data, meta, pool_candidate)
        else:
            save_dataset_and_meta(data, meta)
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
        meta_obj=meta.get(dataset_key),
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
