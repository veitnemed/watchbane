"""Validation helpers for watched record add/update payloads."""

from __future__ import annotations

from dataclasses import dataclass

from config import constant
from common import valid
from dataset.models.identity import duplicate_title_exists
from dataset.models.results import AddRecordResult, UpdateRecordResult
from storage.normalize import (
    is_valid_genre_tags,
    is_valid_tags_vibe,
    normalize_genre_tags,
    normalize_main_info,
    normalize_raw_scores,
    normalize_tags_vibe,
)


@dataclass
class ParsedAddPayload:
    title: str
    main_info: dict
    input_raw_scores: dict
    tags_vibe: dict
    genre_tags: dict
    year: object


def validate_add_record_payload(record_payload: dict, *, data: dict) -> AddRecordResult | ParsedAddPayload:
    """Validate add payload structure and field values."""
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

    if duplicate_title_exists(data, title):
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

    if valid.is_correct_country(str(main_info.get("country", ""))) is False:
        return AddRecordResult(
            ok=False,
            title=title,
            message="Error add movie! Incorrect country",
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

    return ParsedAddPayload(
        title=title,
        main_info=main_info,
        input_raw_scores=input_raw_scores,
        tags_vibe=tags_vibe,
        genre_tags=genre_tags,
        year=year,
    )


def validate_add_features(features: dict, *, title: str) -> AddRecordResult | None:
    required_features = {constant.BIAS_FEATURE, *constant.TAGS_VIBE, *constant.GENRE}
    supported_computed = set(constant.COMPUTED_SCORES) | {"tmdb_score", "tmdb_votes", "tmdb_popularity"}
    supported_features = required_features | supported_computed
    if required_features.issubset(set(features.keys())) is False or set(features.keys()).issubset(supported_features) is False:
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
    return None


def validate_update_patch_structure(
    patch_payload,
    *,
    dataset_title: str,
) -> UpdateRecordResult | None:
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
    return None


def validate_main_info_patch(
    main_patch,
    *,
    dataset_title: str,
    main_info: dict,
) -> UpdateRecordResult | None:
    if main_patch is None:
        return None
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

    allowed_main_fields = {"title", "user_score", "year", "country"}
    unsupported_main = [field for field in main_patch.keys() if field not in allowed_main_fields]
    if len(unsupported_main) > 0:
        return UpdateRecordResult(
            ok=False,
            title=dataset_title,
            message=f"Ошибка обновления! Неподдерживаемые поля main_info: {unsupported_main}",
            reason="invalid_patch",
            changed_fields=[],
        )
    return None


def validate_normalized_update_values(
    *,
    dataset_title: str,
    new_main_info: dict,
    new_raw_scores: dict,
    new_tags_vibe: dict,
    new_genre_tags: dict,
) -> UpdateRecordResult | None:
    if valid.is_correct_score(str(new_main_info["user_score"])) is False:
        return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректное значение user_score", "invalid_patch", [])
    if valid.is_correct_year(str(new_main_info["year"])) is False:
        return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректный год", "invalid_patch", [])
    if valid.is_correct_country(str(new_main_info.get("country", ""))) is False:
        return UpdateRecordResult(False, dataset_title, "Error update record! Incorrect country", "invalid_patch", [])
    if valid.is_valid_raw_meta(new_raw_scores) is False:
        return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректные raw_scores", "invalid_patch", [])
    if is_valid_tags_vibe(new_tags_vibe) is False:
        return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректные tags_vibe", "invalid_patch", [])
    if is_valid_genre_tags(new_genre_tags) is False:
        return UpdateRecordResult(False, dataset_title, "Ошибка обновления! Некорректная genre-разметка", "invalid_patch", [])
    return None


def validate_update_features(features: dict, *, dataset_title: str) -> UpdateRecordResult | None:
    if valid.is_valid_features(features) is False:
        return UpdateRecordResult(
            ok=False,
            title=dataset_title,
            message="Ошибка обновления! Не хватает параметров",
            reason="invalid_patch",
            changed_fields=[],
        )
    return None


def normalize_update_sections(
    *,
    dataset_title: str,
    main_info: dict,
    raw_scores: dict,
    tags_vibe: dict,
    genre_tags: dict,
) -> tuple[dict, dict, dict, dict] | UpdateRecordResult:
    try:
        main_info = dict(main_info)
        main_info["title"] = dataset_title
        return (
            normalize_main_info(main_info),
            normalize_raw_scores(raw_scores),
            normalize_tags_vibe(tags_vibe),
            normalize_genre_tags(genre_tags),
        )
    except (KeyError, TypeError, ValueError):
        return UpdateRecordResult(
            ok=False,
            title=dataset_title,
            message="Ошибка обновления! Patch не проходит нормализацию",
            reason="invalid_patch",
            changed_fields=[],
        )
