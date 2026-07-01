"""Lazy Qt model for the desktop Candidates list."""

from __future__ import annotations

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt

from desktop.candidates.presenters import (
    candidate_detail_identity,
    resolve_local_poster_path_for_candidate,
)


class CandidateListRoles:
    CandidateRole = int(Qt.ItemDataRole.UserRole)
    IdentityRole = int(Qt.ItemDataRole.UserRole) + 1
    PosterPathRole = int(Qt.ItemDataRole.UserRole) + 2


class CandidateListModel(QAbstractListModel):
    """List model that keeps candidate rows and caches poster path lookups."""

    def __init__(self, candidates: list[dict] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._candidates: list[dict] = []
        self._poster_paths_by_identity: dict[str, str | None] = {}
        if candidates:
            self.set_candidates(candidates)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._candidates)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if index.isValid() is False:
            return None
        row = index.row()
        if row < 0 or row >= len(self._candidates):
            return None

        candidate = self._candidates[row]
        if role == int(Qt.ItemDataRole.DisplayRole):
            title = candidate.get("title") or candidate.get("name") or "Без названия"
            year = candidate.get("year") or "?"
            return f"{title} ({year})"
        if role == CandidateListRoles.CandidateRole:
            return candidate
        if role == CandidateListRoles.IdentityRole:
            return candidate_detail_identity(candidate)
        if role == CandidateListRoles.PosterPathRole:
            return self.poster_path_for_candidate(candidate)
        return None

    def roleNames(self) -> dict[int, bytes]:
        roles = super().roleNames()
        roles[CandidateListRoles.CandidateRole] = b"candidate"
        roles[CandidateListRoles.IdentityRole] = b"identity"
        roles[CandidateListRoles.PosterPathRole] = b"posterPath"
        return roles

    def set_candidates(self, candidates: list[dict]) -> None:
        self.beginResetModel()
        self._candidates = list(candidates or [])
        identities = {candidate_detail_identity(candidate) for candidate in self._candidates}
        self._poster_paths_by_identity = {
            identity: path
            for identity, path in self._poster_paths_by_identity.items()
            if identity in identities
        }
        self.endResetModel()

    def candidate_at(self, row: int) -> dict | None:
        if row < 0 or row >= len(self._candidates):
            return None
        return self._candidates[row]

    def row_for_identity(self, identity: str | None) -> int:
        if identity in (None, ""):
            return -1
        for index, candidate in enumerate(self._candidates):
            if candidate_detail_identity(candidate) == identity:
                return index
        return -1

    def poster_path_for_candidate(self, candidate: dict) -> str | None:
        identity = candidate_detail_identity(candidate)
        if identity not in self._poster_paths_by_identity:
            self._poster_paths_by_identity[identity] = resolve_local_poster_path_for_candidate(candidate)
        return self._poster_paths_by_identity.get(identity)

    def update_poster_path(self, identity: str, path: str | None) -> None:
        if identity in (None, ""):
            return
        self._poster_paths_by_identity[str(identity)] = path
        row = self.row_for_identity(str(identity))
        if row < 0:
            return
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, [CandidateListRoles.PosterPathRole])
