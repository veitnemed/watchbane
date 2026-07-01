"""Structured results for watched record operations."""

from dataclasses import dataclass


@dataclass
class AddRecordResult:
    ok: bool
    title: str | None
    message: str
    reason: str | None = None
    side_effects: list[dict] | None = None


@dataclass
class UpdateRecordResult:
    ok: bool
    title: str | None
    message: str
    reason: str | None = None
    changed_fields: list[str] | None = None


@dataclass
class DeleteRecordResult:
    ok: bool
    dataset_key: str | None
    message: str
    reason: str | None = None
    title: str | None = None
    year: object | None = None
    deleted_dataset: int = 0
    deleted_meta: int = 0
    deleted_poster_cache: int = 0
    deleted_poster_file: int = 0
    dataset_count: int = 0
    backups: list[str] | None = None

    def to_dict(self) -> dict:
        payload = {
            "ok": self.ok,
            "message": self.message,
            "deleted_dataset": self.deleted_dataset,
            "deleted_meta": self.deleted_meta,
            "deleted_poster_cache": self.deleted_poster_cache,
            "deleted_poster_file": self.deleted_poster_file,
            "dataset_count": self.dataset_count,
            "backups": self.backups or [],
        }
        if self.title is not None:
            payload["title"] = self.title
        if self.year is not None:
            payload["year"] = self.year
        return payload
