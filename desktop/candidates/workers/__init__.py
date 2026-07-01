"""Background workers for candidate desktop UI."""

from desktop.candidates.workers.poster_worker import CandidatePosterDownloadWorker
from desktop.candidates.workers.search_worker import CandidateSearchWorker

__all__ = ["CandidatePosterDownloadWorker", "CandidateSearchWorker"]
