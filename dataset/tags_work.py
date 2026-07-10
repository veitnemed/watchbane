"""Compatibility wrapper for vibe tag catalog and dataset mutations.

Чистое чтение/валидация каталога тегов живёт в config.tags_work и ре-экспортируется
здесь для обратной совместимости старых импортов ``from dataset import tags_work``.
"""

from config.tags_work import (
    TAGS_JSON,
    get_tag_fields,
    get_tag_labels,
    get_tag_rules,
    get_tag_translations,
    is_correct_tag_name,
    load_json,
    load_tags,
    save_json,
    save_tags,
)
from dataset.tags.backup import backup_tag_files, move_edit_files_to_backup
from dataset.tags.mutations import (
    add_tag,
    add_tag_to_data,
    delete_all_tags,
    delete_tag,
    delete_tag_from_data,
)

__all__ = [
    "TAGS_JSON",
    "add_tag",
    "add_tag_to_data",
    "backup_tag_files",
    "delete_all_tags",
    "delete_tag",
    "delete_tag_from_data",
    "get_tag_fields",
    "get_tag_labels",
    "get_tag_rules",
    "get_tag_translations",
    "is_correct_tag_name",
    "load_json",
    "load_tags",
    "move_edit_files_to_backup",
    "save_json",
    "save_tags",
]
