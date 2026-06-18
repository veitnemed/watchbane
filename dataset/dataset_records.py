"""Central service for adding records to dataset/meta."""

from dataclasses import dataclass

from config import constant
from common import format_score
from common import valid
from storage.data import add_movies_to_meta, get_meta_obj, load_dataset, load_meta, save_dataset, save_meta
from storage.normalize import (
    is_valid_genre_tags,
    is_valid_tags_vibe,
    normalize_genre_tags,
    normalize_main_info,
    normalize_raw_scores,
    normalize_tags_vibe,
)


@dataclass
class AddRecordResult:
    ok: bool
    title: str | None
    message: str
    reason: str | None = None


@dataclass
class UpdateRecordResult:
    ok: bool
    title: str | None
    message: str
    reason: str | None = None
    changed_fields: list[str] | None = None


def _duplicate_title_exists(data: dict, title: str) -> bool:
    expected = title.strip().lower()
    for current_title in data.keys():
        if current_title.strip().lower() == expected:
            return True
    return False


def _find_dataset_title(data: dict, title: str) -> str | None:
    expected = str(title).strip().lower()
    for current_title in data.keys():
        if current_title.strip().lower() == expected:
            return current_title
    return None


def _build_features(computed_scores: dict, tags_vibe: dict, genre_tags: dict) -> dict:
    features = {
        constant.BIAS_FEATURE: 1.0
    }
    for feature in computed_scores:
        features[feature] = computed_scores[feature]
    for feature, value in format_score.tags_to_features(tags_vibe).items():
        features[feature] = value
    for feature, value in format_score.tags_to_features(genre_tags, constant.GENRE_SECTION).items():
        features[feature] = value
    return features


def _find_meta_title(meta: dict, title: str) -> str | None:
    expected = str(title).strip().lower()
    for current_title in meta.keys():
        if current_title.strip().lower() == expected:
            return current_title
    return None


def _sync_raw_scores_to_meta(title: str, main_info: dict, raw_scores: dict) -> None:
    meta = load_meta()
    meta_title = _find_meta_title(meta, title)

    meta_obj = {
        "main_info": normalize_main_info(main_info),
        "raw_scores": normalize_raw_scores(raw_scores),
    }
    if meta_title is None:
        meta[title] = meta_obj
    else:
        current_meta = dict(meta[meta_title])
        current_meta["main_info"] = meta_obj["main_info"]
        current_meta["raw_scores"] = meta_obj["raw_scores"]
        meta[meta_title] = current_meta

    save_meta(meta)


def _extract_extra_meta(meta_payload) -> dict:
    if isinstance(meta_payload, dict) is False:
        return {}

    extra_meta = {}
    for key, value in meta_payload.items():
        if key in {"main_info", "raw_scores"}:
            continue
        extra_meta[key] = value
    return extra_meta


def _cleanup_candidate_pool(pool_candidate=None) -> None:
    try:
        from candidates import candidate_pool

        if pool_candidate is not None:
            candidate_pool.remove_candidate_from_pool(pool_candidate)
            return

        pool = candidate_pool.load_candidate_pool()
        pool = candidate_pool.remove_watched_candidates(pool)
        candidate_pool.save_candidate_pool(pool)
    except Exception:
        pass


def add_dataset_record(
    record_payload: dict,
    meta_payload=None,
    source_name: str = "",
    pool_candidate=None,
) -> AddRecordResult:
    """Adds a new record to dataset using the current add_movie behavior."""
    try:
        main_info = record_payload["main_info"]
        input_raw_scores = record_payload["raw_scores"]
    except (KeyError, TypeError):
        return AddRecordResult(
            ok=False,
            title=None,
            message="Ошибка добавления! Некорректная структура записи",
            reason="invalid_payload",
        )

    title = str(main_info.get("title", "")).strip()
    if title == "":
        return AddRecordResult(
            ok=False,
            title=None,
            message="Ошибка добавления! Некорректное название",
            reason="empty_title",
        )

    try:
        tags_vibe = normalize_tags_vibe(record_payload[constant.TAGS_VIBE_SECTION])
        genre_tags = normalize_genre_tags(record_payload.get(constant.GENRE_SECTION, {}))
        user_score = main_info["user_score"]
        year = main_info["year"]
    except (KeyError, TypeError, ValueError):
        return AddRecordResult(
            ok=False,
            title=title,
            message="Ошибка добавления! Некорректная структура записи",
            reason="invalid_payload",
        )

    if valid.is_correct_title(title) is False:
        return AddRecordResult(
            ok=False,
            title=title,
            message="Ошибка добавления! Некорректное название",
            reason="empty_title",
        )

    data = load_dataset()
    if _duplicate_title_exists(data, title):
        return AddRecordResult(
            ok=False,
            title=title,
            message="Ошибка добавления! Такой объект уже добавлен",
            reason="duplicate_title",
        )

    if valid.is_correct_score(str(user_score)) is False:
        return AddRecordResult(
            ok=False,
            title=title,
            message="Ошибка добавления! Некорректное значение user_score",
            reason="invalid_payload",
        )

    if valid.is_correct_year(str(year)) is False:
        return AddRecordResult(
            ok=False,
            title=title,
            message="Error add movie! Incorrect year",
            reason="invalid_payload",
        )

    if is_valid_tags_vibe(tags_vibe) is False:
        return AddRecordResult(
            ok=False,
            title=title,
            message="Ошибка добавления! Некорректные tags_vibe",
            reason="invalid_payload",
        )

    if is_valid_genre_tags(genre_tags) is False:
        return AddRecordResult(
            ok=False,
            title=title,
            message="Ошибка добавления! Некорректная жанровая разметка",
            reason="invalid_payload",
        )

    extra_meta = _extract_extra_meta(meta_payload)
    meta_obj = None
    if isinstance(meta_payload, dict) and (
        "raw_scores" in meta_payload or "raw" in meta_payload
    ):
        meta_obj = meta_payload
    else:
        meta_obj = get_meta_obj(title)
    if meta_obj is None:
        if valid.is_valid_raw_meta(input_raw_scores) is False:
            return AddRecordResult(
                ok=False,
                title=title,
                message="Ошибка добавления! Некорректные raw_scores",
                reason="invalid_payload",
            )

        raw_scores = normalize_raw_scores(input_raw_scores)
        if add_movies_to_meta(main_info, raw_scores, extra_meta=extra_meta) is False:
            return AddRecordResult(
                ok=False,
                title=title,
                message="Ошибка добавления! Некорректные meta-данные",
                reason="invalid_payload",
            )
    else:
        raw_scores = meta_obj.get("raw_scores", meta_obj.get("raw"))
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
    computed_scores = format_score.raw_to_struct(raw_scores, new_main_info)
    features = {
        constant.BIAS_FEATURE: 1.0
    }
    for feature in computed_scores:
        features[feature] = computed_scores[feature]
    for feature, value in format_score.tags_to_features(tags_vibe).items():
        features[feature] = value
    for feature, value in format_score.tags_to_features(genre_tags, constant.GENRE_SECTION).items():
        features[feature] = value

    if valid.is_valid_features(features) is False:
        return AddRecordResult(
            ok=False,
            title=title,
            message=(
                "Ошибка добавления! Не хватает параметров\n"
                f"Ожидались: {constant.FEATURES}\n"
                f"Получены: {list(features.keys())}"
            ),
            reason="invalid_payload",
        )

    new_movie = {}
    new_movie["main_info"] = new_main_info
    new_movie["raw_scores"] = raw_scores
    new_movie["computed_scores"] = computed_scores
    new_movie[constant.TAGS_VIBE_SECTION] = tags_vibe
    new_movie[constant.GENRE_SECTION] = genre_tags

    data[title] = new_movie
    try:
        save_dataset(data)
    except Exception as error:
        return AddRecordResult(
            ok=False,
            title=title,
            message=f"Ошибка добавления! Не удалось сохранить dataset: {error}",
            reason="save_error",
        )

    _cleanup_candidate_pool(pool_candidate)
    return AddRecordResult(
        ok=True,
        title=title,
        message="Новая запись добавлена!",
        reason="saved",
    )


def update_dataset_record(title, patch_payload, source_name: str = "") -> UpdateRecordResult:
    """Updates safe fields of an existing dataset record without changing its key."""
    data = load_dataset()
    dataset_title = _find_dataset_title(data, title)
    if dataset_title is None:
        return UpdateRecordResult(
            ok=False,
            title=str(title).strip() if title is not None else None,
            message="Ошибка обновления! Запись не найдена",
            reason="not_found",
            changed_fields=[],
        )

    if isinstance(patch_payload, dict) is False:
        return UpdateRecordResult(
            ok=False,
            title=dataset_title,
            message="Ошибка обновления! Некорректный patch",
            reason="invalid_patch",
            changed_fields=[],
        )

    allowed_sections = {"main_info", "raw_scores", constant.TAGS_VIBE_SECTION, constant.GENRE_SECTION}
    unsupported_sections = [section for section in patch_payload.keys() if section not in allowed_sections]
    if len(unsupported_sections) > 0:
        return UpdateRecordResult(
            ok=False,
            title=dataset_title,
            message=f"Ошибка обновления! Неподдерживаемые секции: {unsupported_sections}",
            reason="invalid_patch",
            changed_fields=[],
        )

    current_movie = data[dataset_title]
    main_info = dict(current_movie.get("main_info", {}))
    raw_scores = dict(current_movie.get("raw_scores", {}))
    tags_vibe = dict(current_movie.get(constant.TAGS_VIBE_SECTION, {}))
    genre_tags = dict(current_movie.get(constant.GENRE_SECTION, {}))
    changed_fields = []

    main_patch = patch_payload.get("main_info")
    if main_patch is not None:
        if isinstance(main_patch, dict) is False:
            return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректный main_info", "invalid_patch", [])

        if "title" in main_patch:
            new_title = str(main_patch.get("title") or "").strip()
            current_title = str(main_info.get("title", dataset_title)).strip()
            if new_title != "" and new_title.lower() != current_title.lower():
                return UpdateRecordResult(
                    ok=False,
                    title=dataset_title,
                    message="Ошибка обновления! Переименование делается только через отдельный пункт \"Переименовать запись\".",
                    reason="title_change_forbidden",
                    changed_fields=[],
                )

        allowed_main_fields = {"title", "user_score", "year"}
        unsupported_main = [field for field in main_patch.keys() if field not in allowed_main_fields]
        if len(unsupported_main) > 0:
            return UpdateRecordResult(
                ok=False,
                title=dataset_title,
                message=f"Ошибка обновления! Неподдерживаемые поля main_info: {unsupported_main}",
                reason="invalid_patch",
                changed_fields=[],
            )

        for field in ("user_score", "year"):
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

    tags_patch = patch_payload.get(constant.TAGS_VIBE_SECTION)
    if tags_patch is not None:
        if isinstance(tags_patch, dict) is False:
            return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректные tags_vibe", "invalid_patch", [])
        for field, value in tags_patch.items():
            if field not in constant.TAGS_VIBE:
                return UpdateRecordResult(
                    ok=False,
                    title=dataset_title,
                    message=f"Ошибка обновления! Неподдерживаемое поле tags_vibe: {field}",
                    reason="invalid_patch",
                    changed_fields=[],
                )
            if tags_vibe.get(field) != value:
                tags_vibe[field] = value
                changed_fields.append(f"{constant.TAGS_VIBE_SECTION}.{field}")

    genre_patch = patch_payload.get(constant.GENRE_SECTION)
    if genre_patch is not None:
        if isinstance(genre_patch, dict) is False:
            return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректная genre-разметка", "invalid_patch", [])
        for field, value in genre_patch.items():
            if field not in constant.GENRE:
                return UpdateRecordResult(
                    ok=False,
                    title=dataset_title,
                    message=f"Ошибка обновления! Неподдерживаемое поле genre: {field}",
                    reason="invalid_patch",
                    changed_fields=[],
                )
            if genre_tags.get(field) != value:
                genre_tags[field] = value
                changed_fields.append(f"{constant.GENRE_SECTION}.{field}")

    if len(changed_fields) == 0:
        if raw_patch is not None:
            try:
                current_main_info = normalize_main_info({**main_info, "title": dataset_title})
                current_raw_scores = normalize_raw_scores(raw_scores)
                _sync_raw_scores_to_meta(dataset_title, current_main_info, current_raw_scores)
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

    try:
        main_info["title"] = dataset_title
        new_main_info = normalize_main_info(main_info)
        new_raw_scores = normalize_raw_scores(raw_scores)
        new_tags_vibe = normalize_tags_vibe(tags_vibe)
        new_genre_tags = normalize_genre_tags(genre_tags)
    except (KeyError, TypeError, ValueError):
        return UpdateRecordResult(
            ok=False,
            title=dataset_title,
            message="Ошибка обновления! Patch не проходит нормализацию",
            reason="invalid_patch",
            changed_fields=[],
        )

    if valid.is_correct_score(str(new_main_info["user_score"])) is False:
        return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректное значение user_score", "invalid_patch", [])
    if valid.is_correct_year(str(new_main_info["year"])) is False:
        return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректный год", "invalid_patch", [])
    if valid.is_valid_raw_meta(new_raw_scores) is False:
        return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректные raw_scores", "invalid_patch", [])
    if is_valid_tags_vibe(new_tags_vibe) is False:
        return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректные tags_vibe", "invalid_patch", [])
    if is_valid_genre_tags(new_genre_tags) is False:
        return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректная genre-разметка", "invalid_patch", [])

    computed_scores = format_score.raw_to_struct(new_raw_scores, new_main_info)
    features = _build_features(computed_scores, new_tags_vibe, new_genre_tags)
    if valid.is_valid_features(features) is False:
        return UpdateRecordResult(
            ok=False,
            title=dataset_title,
            message="Ошибка обновления! Не хватает параметров",
            reason="invalid_patch",
            changed_fields=[],
        )

    updated_movie = {}
    updated_movie["main_info"] = new_main_info
    updated_movie["raw_scores"] = new_raw_scores
    updated_movie["computed_scores"] = computed_scores
    updated_movie[constant.TAGS_VIBE_SECTION] = new_tags_vibe
    updated_movie[constant.GENRE_SECTION] = new_genre_tags
    data[dataset_title] = updated_movie

    try:
        save_dataset(data)
        if raw_patch is not None:
            _sync_raw_scores_to_meta(dataset_title, new_main_info, new_raw_scores)
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
