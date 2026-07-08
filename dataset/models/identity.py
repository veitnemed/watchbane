"""Case-insensitive title/key lookup for watched dataset and meta."""

from dataset.models.media_type import normalize_media_type


def normalize_title_key(title: str) -> str:
    """Normalize a title for case-insensitive comparison."""
    return str(title).strip().lower()


def normalize_year_key(year) -> str:
    """Normalize a year for identity comparison."""
    return str(year or "").strip()


def get_record_main_info(record: dict | None) -> dict:
    if isinstance(record, dict) is False:
        return {}
    main_info = record.get("main_info")
    return main_info if isinstance(main_info, dict) else {}


def get_record_title(dataset_key: str, record: dict | None) -> str:
    main_info = get_record_main_info(record)
    return str(main_info.get("title") or dataset_key).strip()


def get_record_year(record: dict | None):
    return get_record_main_info(record).get("year")


def get_record_media_type(record: dict | None) -> str:
    main_info = get_record_main_info(record)
    media_type = main_info.get("media_type")
    if media_type in (None, "") and isinstance(record, dict):
        media_type = record.get("media_type")
    return normalize_media_type(media_type)


def same_record_identity(
    *,
    dataset_key: str,
    record: dict | None,
    title: str,
    year=None,
    media_type=None,
) -> bool:
    """Return True when record matches title/year/media_type identity."""
    if normalize_title_key(get_record_title(dataset_key, record)) != normalize_title_key(title):
        return False
    if get_record_media_type(record) != normalize_media_type(media_type):
        return False

    expected_year = normalize_year_key(year)
    current_year = normalize_year_key(get_record_year(record))
    if expected_year == "" or current_year == "":
        return True
    return current_year == expected_year


def find_case_insensitive_key(mapping: dict, title: str) -> str | None:
    """Return the actual dict key matching title (strip + casefold)."""
    expected = normalize_title_key(title)
    for current_key in mapping.keys():
        if normalize_title_key(current_key) == expected:
            return current_key
    return None


def find_dataset_title(data: dict, title: str, *, year=None, media_type=None) -> str | None:
    """Return the dataset key for a title identity, or None if not found."""
    if year is None and media_type is None:
        return find_case_insensitive_key(data, title)
    for dataset_key, record in data.items():
        if same_record_identity(
            dataset_key=dataset_key,
            record=record,
            title=title,
            year=year,
            media_type=media_type,
        ):
            return dataset_key
    return None


def duplicate_title_exists(data: dict, title: str, *, year=None, media_type=None) -> bool:
    """Return True if a duplicate title identity exists in dataset."""
    return find_dataset_title(data, title, year=year, media_type=media_type) is not None


def build_dataset_record_key(data: dict, title: str, *, year=None, media_type=None) -> str:
    """Build a stable dataset key without overwriting a different media identity."""
    title = str(title).strip()
    if find_case_insensitive_key(data, title) is None:
        return title

    normalized_media_type = normalize_media_type(media_type)
    normalized_year = normalize_year_key(year)
    suffix_parts = [part for part in (normalized_year, normalized_media_type) if part]
    suffix = ", ".join(suffix_parts) or normalized_media_type
    base_key = f"{title} ({suffix})"
    if find_case_insensitive_key(data, base_key) is None:
        return base_key

    index = 2
    while True:
        candidate_key = f"{base_key} #{index}"
        if find_case_insensitive_key(data, candidate_key) is None:
            return candidate_key
        index += 1
