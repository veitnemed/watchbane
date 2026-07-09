"""Action orchestration for CandidateListView."""

from __future__ import annotations

import logging

from desktop.candidates.presenters import candidate_detail_identity
from desktop.candidates.workers.poster_worker import CandidatePosterDownloadWorker

logger = logging.getLogger(__name__)


class CandidateListActionsMixin:
    """Transfer, hide and poster-worker actions for CandidateListView."""

    # Expected CandidateListView attributes:
    # _show_status, _list_widget/_results_list, _selected_candidate, _selected_identity,
    # _on_watched_added callbacks, _session/_service state, _detail_entries,
    # _detail_card, _model, _widget, _poster_request_seq, _poster_worker.

    def _candidate_rank(self, candidate: dict) -> int | None:
        candidates = getattr(self, "_candidates", None) or []
        try:
            target = candidate_detail_identity(candidate)
        except Exception:
            return None
        for index, item in enumerate(candidates, start=1):
            if candidate_detail_identity(item) == target:
                return index
        return None

    def _log_search_action(self, action: str, candidate: dict, rank: int | None = None) -> None:
        """Best-effort action breadcrumb (open/hide/watched) tied to a search_id."""
        try:
            from candidates.search import query_log

            if not query_log.is_search_query_log_enabled():
                return
            context = self._session.last_search_context() or {}
            if rank is None:
                rank = self._candidate_rank(candidate)
            tmdb_id = candidate.get("tmdb_id")
            if tmdb_id in (None, ""):
                source_query = candidate.get("source_query")
                if isinstance(source_query, dict):
                    tmdb_id = source_query.get("tmdb_id")
            entry = query_log.build_search_action_entry(
                search_id=context.get("search_id"),
                action=action,
                tmdb_id=tmdb_id,
                rank=rank,
                query=getattr(self, "_search_input", None).text()
                if getattr(self, "_search_input", None) is not None
                else "",
            )
            query_log.append_search_query_log(entry)
        except Exception:
            logger.debug("search action logging skipped", exc_info=True)

    def _transfer_selected_to_watched(self) -> None:
        candidate = self._selected_candidate
        if not isinstance(candidate, dict):
            return

        from desktop.watched.add_title import run_candidate_transfer_flow

        parent = self._widget.window()
        result = run_candidate_transfer_flow(parent, candidate)
        if result is None or getattr(result, "ok", False) is False:
            return

        self._log_search_action("watched", candidate)
        self._selected_candidate = None
        if self._session.filters is not None:
            self._session.reload_from_pool(force=True)
        if self._on_watched_added is not None:
            self._on_watched_added(result)

    def _hide_selected_candidate(self) -> None:
        candidate = self._selected_candidate
        if not isinstance(candidate, dict):
            return

        result = self._service.hide_candidate(candidate)
        if isinstance(result, dict) and result.get("ok") is False:
            return

        self._log_search_action("hide", candidate)
        identity = candidate_detail_identity(candidate)
        self._detail_entries.pop(identity, None)
        self._selected_candidate = None
        self._selected_identity = None
        self._session.remove_candidate(candidate)

    def _start_poster_download(self, poster_url: str, identity: str, request_seq: int) -> None:
        worker = CandidatePosterDownloadWorker(poster_url, parent=self._widget)
        worker.finished_with_path.connect(
            lambda local_path, seq=request_seq, ident=identity: self._on_poster_download_finished(
                seq,
                ident,
                local_path,
            )
        )
        worker.finished.connect(worker.deleteLater)
        self._poster_worker = worker
        worker.start()

    def _on_poster_download_finished(self, request_seq: int, identity: str, local_path: str) -> None:
        if request_seq != self._poster_request_seq:
            return

        entry = self._detail_entries.get(identity)
        if entry is not None:
            entry_key, movie, card = entry
            updated_card = dict(card)
            updated_card["poster_path"] = local_path
            updated_card["poster_src"] = local_path
            self._detail_entries[identity] = (entry_key, movie, updated_card)

        self._detail_card.apply_local_poster_path(local_path)
        self._model.update_poster_path(identity, local_path)
        self._results_list.viewport().update()
