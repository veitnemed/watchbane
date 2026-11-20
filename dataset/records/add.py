"""Add watched record use-case."""

from copy import deepcopy

from common import valid
from dataset.meta.merge import extract_extra_meta
from dataset.models.results import AddRecordResult
from dataset.records.features import build_computed_scores
from dataset.records.side_effects import run_after_add_side_effects
from dataset.records.validation import validate_add_record_payload
from storage.normalize import normalize_main_info, normalize_raw_scores


_LEGACY_RAW_FIELDS = {
    "kp_score", "kp_votes", "kp_popularity", "imdb_score", "imdb_votes", "imdb_popularity",
}


def _positive_tmdb_id(value):
    if type(value) is int:
        return value if value > 0 else None
    if type(value) is str and (text := value.strip()).isascii() and text.isdecimal() and len(text) <= 20:
        number = int(text)
        return number if number > 0 else None
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


def _build_new_movie(record_payload, main_info, raw_scores):
    main_info = normalize_main_info(main_info)
    raw_scores = normalize_raw_scores(raw_scores)
    movie = {
        "main_info": main_info,
        "raw_scores": raw_scores,
        "computed_scores": build_computed_scores(raw_scores, main_info),
    }
    localized = record_payload.get("localized")
    if isinstance(localized, dict):
        movie["localized"] = deepcopy(localized)
    genres_tmdb = record_payload.get("genres_tmdb")
    if isinstance(genres_tmdb, list) and genres_tmdb:
        movie["genres_tmdb"] = list(genres_tmdb)
    return movie


def _persist_one_watched(data, meta, candidate):
    from candidates.title_state_service import save_watched_dataset_transition
    return save_watched_dataset_transition(data, meta, candidate)


def add_dataset_record(
    record_payload: dict,
    meta_payload=None,
    source_name: str = "",
    pool_candidate=None,
    poster_hints=None,
) -> AddRecordResult:
    """Add one watched record without rewriting the rest of the collection."""
    from candidates.title_state_service import ReviewedWatchedConflict

    # Decide duplicates and allocate the key against fresh state inside SQLite,
    # not against a whole-library snapshot read when the form was prepared.
    parsed = validate_add_record_payload(record_payload, data={})
    if isinstance(parsed, AddRecordResult):
        return parsed
    raw = (meta_payload.get("raw_scores", meta_payload.get("raw", parsed.input_raw_scores))
           if isinstance(meta_payload, dict) else parsed.input_raw_scores)
    if not isinstance(raw, dict):
        return AddRecordResult(False, parsed.title, "Ошибка добавления! Некорректные raw_scores", "invalid_payload")
    extra_meta = extract_extra_meta(meta_payload)
    values = (extra_meta.get("tmdb_id"), raw.get("tmdb_id"))
    ids = {clean for value in values if (clean := _positive_tmdb_id(value)) is not None}
    if len(ids) > 1:
        return AddRecordResult(False, parsed.title, "В метаданных указаны разные TMDb ID.", "invalid_payload")
    if ids:
        extra_meta["tmdb_id"] = ids.pop()
    # The old legacy-cache path accepted but did not persist external scores.
    raw = {key: value for key, value in raw.items() if key not in _LEGACY_RAW_FIELDS and key != "tmdb_id"}
    if not valid.is_valid_raw_meta(raw):
        return AddRecordResult(False, parsed.title, "Ошибка добавления! Некорректные raw_scores", "invalid_payload")
    meta = _build_meta_obj(parsed.main_info, raw, extra_meta=extra_meta)
    if meta is None:
        return AddRecordResult(False, parsed.title, "Ошибка добавления! Некорректные meta-данные", "invalid_payload")
    movie = _build_new_movie(record_payload, parsed.main_info, raw)
    try:
        candidate = pool_candidate if isinstance(pool_candidate, dict) else None
        persisted = _persist_one_watched({parsed.title: movie}, {parsed.title: meta}, candidate)
    except ReviewedWatchedConflict as error:
        return AddRecordResult(False, error.dataset_key, str(error), error.reason)
    except Exception as error:
        return AddRecordResult(False, parsed.title, f"Ошибка добавления! Не удалось сохранить dataset: {error}", "save_error")

    dataset_key = parsed.title
    if persisted is not None:
        dataset_key, movie, meta = persisted.dataset_key, persisted.payload, persisted.meta
    side_effects = run_after_add_side_effects(
        title=parsed.title, year=parsed.year, movie=movie, meta_obj=meta,
        pool_candidate=pool_candidate, poster_hints=poster_hints,
    )
    return AddRecordResult(True, dataset_key, "Новая запись добавлена!", "saved", side_effects)
