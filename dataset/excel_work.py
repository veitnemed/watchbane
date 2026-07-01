"""Compatibility wrapper for Excel export/import."""

from dataset.excel.export import export_dataset_to_excel
from dataset.excel.import_flow import (
    build_patch_payload,
    load_movies_from_excel,
    print_excel_import_forbidden_message,
    replace_dataset_from_excel,
    validate_excel_titles,
)
from dataset.excel.rows import apply_header_column_widths, build_row
from dataset.excel.schema import SHEET_NAME, get_excel_headers, is_excel_schema_actual, move_excel_to_backup

__all__ = [
    "SHEET_NAME",
    "apply_header_column_widths",
    "build_patch_payload",
    "build_row",
    "export_dataset_to_excel",
    "get_excel_headers",
    "is_excel_schema_actual",
    "load_movies_from_excel",
    "move_excel_to_backup",
    "print_excel_import_forbidden_message",
    "replace_dataset_from_excel",
    "validate_excel_titles",
]
