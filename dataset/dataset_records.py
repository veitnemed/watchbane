"""Compatibility wrapper for watched record add/update."""

from dataset.models.results import AddRecordResult, UpdateRecordResult
from dataset.records.add import add_dataset_record
from dataset.records.update import update_dataset_record

__all__ = [
    "AddRecordResult",
    "UpdateRecordResult",
    "add_dataset_record",
    "update_dataset_record",
]
