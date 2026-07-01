from config import constant
from dataset.models.results import AddRecordResult, UpdateRecordResult
from dataset.records.validation import (
    ParsedAddPayload,
    validate_add_record_payload,
    validate_main_info_patch,
    validate_update_patch_structure,
)


def _valid_add_payload(title: str = "New Title") -> dict:
    return {
        "main_info": {
            "title": title,
            "user_score": 8.0,
            "year": 2020,
            "country": "Россия",
        },
        "raw_scores": {
            "kp_score": 8.0,
            "kp_votes": 1000,
            "imdb_score": 8.0,
            "imdb_votes": 100,
        },
        constant.TAGS_VIBE_SECTION: {feature: 0 for feature in constant.TAGS_VIBE},
        constant.GENRE_SECTION: {feature: 0 for feature in constant.GENRE},
    }


def test_validate_add_record_payload_accepts_valid_payload() -> None:
    result = validate_add_record_payload(_valid_add_payload(), data={})
    assert isinstance(result, ParsedAddPayload)
    assert result.title == "New Title"


def test_validate_add_record_payload_rejects_duplicate() -> None:
    result = validate_add_record_payload(_valid_add_payload("Alpha"), data={"Alpha": {}})
    assert isinstance(result, AddRecordResult)
    assert result.ok is False
    assert result.reason == "duplicate_title"


def test_validate_update_patch_structure_rejects_unknown_section() -> None:
    result = validate_update_patch_structure({"computed_scores": {}}, dataset_title="Alpha")
    assert isinstance(result, UpdateRecordResult)
    assert result.reason == "invalid_patch"


def test_validate_main_info_patch_forbids_rename() -> None:
    result = validate_main_info_patch(
        {"title": "Beta"},
        dataset_title="Alpha",
        main_info={"title": "Alpha"},
    )
    assert isinstance(result, UpdateRecordResult)
    assert result.reason == "title_change_forbidden"
