"""Explicit opt-in installation of the pinned, portable E5 model."""
from collections.abc import Callable
from contextlib import closing
from hashlib import sha256
from http.client import HTTPException
from os import fsync, link
from pathlib import Path
from stat import FILE_ATTRIBUTE_REPARSE_POINT
import ssl
from tempfile import TemporaryDirectory
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from candidates.story_model_manifest import MODEL_ID, PORTABLE_FILES, REVISION
from config.app_paths import build_app_paths, get_app_paths


DOWNLOAD_BYTE_LIMIT = 500_000_000
SOCKET_TIMEOUT_SECONDS = 25
TOTAL_TIMEOUT_SECONDS = 30 * 60
_CHUNK_SIZE = 1024 * 1024
_REDIRECT_LIMIT = 4
_REPAIR_SLOTS = 3
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
# Exact hosts only. The CDN is declared in the Hugging Face download docs and
# serves both pinned artifacts on the native acceptance runner.
_ALLOWED_HOSTS = frozenset({"huggingface.co", "cas-bridge.xethub.hf.co", "us.aws.cdn.hf.co"})


class StoryModelInstallError(RuntimeError):
    """The model was not installed; an existing destination was not changed."""

    def __init__(self, message: str, code: str = "runtime_error"):
        super().__init__(message)
        self.code = code


class StoryModelInstallCancelled(StoryModelInstallError):
    """The requested model installation was cancelled."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def profile_story_model_destination(profile_root: Path | None = None) -> Path:
    """Return the stable FP32 destination inside the running profile's cache."""
    paths = get_app_paths() if profile_root is None else build_app_paths(profile_root)
    return paths.cache_dir / "story-models" / f"multilingual-e5-small-{REVISION}-fp32"


def profile_story_model_repair_destination(profile_root: Path) -> Path:
    """Return the alternate managed FP32 slot for explicit repairs."""
    original = profile_story_model_destination(profile_root)
    return original.with_name(original.name + "-repair")


def _check_cancel(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        raise StoryModelInstallCancelled("Model installation cancelled", "cancelled")


def _check_active(cancelled: Callable[[], bool] | None, deadline: float) -> None:
    _check_cancel(cancelled)
    if monotonic() >= deadline:
        raise StoryModelInstallError("Model download timed out", "timeout")


def _raise_idle_timeout(cancelled: Callable[[], bool] | None, deadline: float) -> None:
    # A connect/read capped by the remaining total budget can expire exactly
    # at the deadline; report deadline (or cancellation) before idle timeout.
    _check_active(cancelled, deadline)
    raise StoryModelInstallError("Model connection timed out waiting for data", "idle_timeout") from None


def _safe_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname in _ALLOWED_HOSTS
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
        )
    except ValueError:
        return False


def _open_artifact(opener, name: str, cancelled: Callable[[], bool] | None, deadline: float):
    url = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}"
    for _ in range(_REDIRECT_LIMIT + 1):
        _check_active(cancelled, deadline)
        if not _safe_url(url):
            raise StoryModelInstallError("Unapproved model download address", "redirect_host")
        request = Request(url, headers={"Accept-Encoding": "identity", "User-Agent": "Watchbane"}, method="GET")
        try:
            response = opener.open(request, timeout=min(SOCKET_TIMEOUT_SECONDS, max(0.001, deadline - monotonic())))
        except HTTPError as exc:
            with closing(exc):
                if exc.code not in _REDIRECT_STATUSES:
                    raise StoryModelInstallError(f"Model server returned HTTP {exc.code}", "http_status") from None
                location = exc.headers.get("Location")
                if not location:
                    raise StoryModelInstallError("Model server returned an empty redirect", "invalid_response") from None
                url = urljoin(url, location)
                continue
        except TimeoutError:
            _raise_idle_timeout(cancelled, deadline)
        except URLError as error:
            if not isinstance(error.reason, TimeoutError):
                raise
            _raise_idle_timeout(cancelled, deadline)
        if response.status != 200:
            response.close()
            raise StoryModelInstallError("Model server did not return a complete artifact", "invalid_response")
        return response
    raise StoryModelInstallError("Too many model download redirects", "redirect_host")


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)
    except FileNotFoundError:
        return False


def _verified_existing(destination: Path, cancelled: Callable[[], bool] | None, deadline: float) -> int | None:
    if _is_link_or_reparse(destination) or not destination.is_dir():
        return None
    total = 0
    for name, expected in PORTABLE_FILES.items():
        file = destination / name
        _check_active(cancelled, deadline)
        if _is_link_or_reparse(file) or _is_link_or_reparse(file.parent) or not file.is_file():
            return None
        digest = sha256()
        with file.open("rb") as handle:
            while chunk := handle.read(_CHUNK_SIZE):
                _check_active(cancelled, deadline)
                total += len(chunk)
                if total > DOWNLOAD_BYTE_LIMIT:
                    return None
                digest.update(chunk)
        if digest.hexdigest() != expected:
            return None
    return total


def _download_set(stage, cancelled, deadline, on_progress) -> int:
    transferred = 0
    opener = build_opener(_NoRedirect)
    for name, expected in PORTABLE_FILES.items():
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256()
        with closing(_open_artifact(opener, name, cancelled, deadline)) as response, path.open("xb") as output:
            if response.headers.get("Content-Encoding", "identity").strip().lower() != "identity":
                raise StoryModelInstallError("Unexpected compression for the pinned artifact", "invalid_response")
            size = response.headers.get("Content-Length")
            if size is not None and (not size.isascii() or not size.isdecimal() or len(size) > 12):
                raise StoryModelInstallError("Invalid model artifact size header", "invalid_response")
            declared = int(size) if size is not None else None
            if declared is not None and not 0 < declared <= DOWNLOAD_BYTE_LIMIT - transferred:
                raise StoryModelInstallError("Model exceeds the download size limit", "invalid_response")
            written = 0
            while True:
                _check_active(cancelled, deadline)
                try:
                    chunk = response.read1(_CHUNK_SIZE)
                except TimeoutError:
                    _raise_idle_timeout(cancelled, deadline)
                _check_active(cancelled, deadline)
                if not chunk:
                    break
                written += len(chunk)
                transferred += len(chunk)
                if transferred > DOWNLOAD_BYTE_LIMIT or (declared is not None and written > declared):
                    raise StoryModelInstallError("Model exceeds the download size limit", "invalid_response")
                digest.update(chunk)
                output.write(chunk)
                if on_progress is not None:
                    on_progress(transferred, DOWNLOAD_BYTE_LIMIT)
            if declared is not None and declared != written:
                raise StoryModelInstallError("Model artifact download was incomplete", "integrity")
            if not written or digest.hexdigest() != expected:
                raise StoryModelInstallError(f"Checksum mismatch: {name}", "integrity")
            output.flush()
            fsync(output.fileno())
    return transferred


def install_story_model(
    destination: Path,
    *,
    on_progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> Path:
    """Download the exact portable manifest and publish only the complete set.

    Progress reports downloaded bytes against the transfer cap until installation
    completes, then reports the actual total twice. A verified existing set
    requires no network. Cancellation is observed between reads and before publish.
    """
    return _install_story_model(destination, on_progress=on_progress, cancelled=cancelled)


def repair_profile_story_model(
    profile_root: Path,
    *,
    on_progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> Path:
    """Use a separate managed slot; never inspect or write the old model."""
    _check_cancel(cancelled)
    first = profile_story_model_repair_destination(profile_root)
    deadline = monotonic() + TOTAL_TIMEOUT_SECONDS
    free = None
    try:
        _check_repair_ancestors(first)
        for index in range(1, _REPAIR_SLOTS + 1):
            alternate = first if index == 1 else first.with_name(f"{first.name}-{index}")
            _check_active(cancelled, deadline)
            try:
                alternate.lstat()
            except FileNotFoundError:
                if free is None:
                    free = alternate
                continue
            except OSError:
                continue  # An inaccessible slot is not available for writing.
            try:
                verified = _verified_existing(alternate, cancelled, deadline)
            except OSError:
                continue
            if verified is not None:
                if on_progress is not None:
                    on_progress(verified, verified)
                return alternate
        if free is None:
            raise StoryModelInstallError("Managed repairs are occupied; choose a verified model folder", "existing_invalid")
    except StoryModelInstallError:
        raise
    except OSError:
        raise StoryModelInstallError("Could not access managed model repairs", "network_or_disk") from None
    return _install_story_model(free, on_progress=on_progress, cancelled=cancelled, repair=True, deadline=deadline)


def _check_repair_ancestors(destination: Path) -> None:
    for folder in (destination.parent.parent, destination.parent):
        if _is_link_or_reparse(folder):
            raise StoryModelInstallError("Managed cache is redirected; it was not changed", "existing_invalid")


def _publish_repair(stage: Path, destination: Path, cancelled, deadline) -> bool:
    # Directory renames can replace an empty directory on POSIX; reserve the
    # alternate explicitly instead. Other processes may see an incomplete slot
    # during publish, but none will adopt it without verifying the full set.
    try:
        destination.mkdir()
    except FileExistsError:
        return False
    created_files = []
    created_dirs = [destination]
    try:
        for name in PORTABLE_FILES:
            _check_active(cancelled, deadline)
            target = destination / name
            if target.parent not in created_dirs:
                target.parent.mkdir()
                created_dirs.append(target.parent)
            try:
                link(stage / name, target)
                created_files.append(target)
            except FileExistsError:
                raise
            except OSError:
                # e.g. FAT volumes cannot hardlink. Exclusive opens still
                # prevent clobbering, and the abort cleanup owns only our files.
                with target.open("xb") as output:
                    created_files.append(target)
                    with (stage / name).open("rb") as source:
                        while chunk := source.read(_CHUNK_SIZE):
                            _check_active(cancelled, deadline)
                            output.write(chunk)
                    output.flush()
                    fsync(output.fileno())
        if _verified_existing(destination, cancelled, deadline) is None:
            raise StoryModelInstallError("Repaired model could not be verified", "integrity")
    except BaseException:
        for path in reversed(created_files):
            try:
                path.unlink()
            except OSError:
                pass
        for path in reversed(created_dirs):
            try:
                path.rmdir()
            except OSError:
                pass
        raise
    return True


def _install_story_model(destination: Path, *, on_progress, cancelled, repair=False, deadline=None) -> Path:
    if deadline is None:
        deadline = monotonic() + TOTAL_TIMEOUT_SECONDS
    destination = Path(destination).expanduser().absolute()
    _check_cancel(cancelled)
    try:
        if repair:
            _check_repair_ancestors(destination)
        if destination.exists() or _is_link_or_reparse(destination):
            existing = _verified_existing(destination, cancelled, deadline)
            if existing is None:
                raise StoryModelInstallError("Model destination exists but could not be verified; it was not changed", "existing_invalid")
            if on_progress is not None:
                on_progress(existing, existing)
            return destination

        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".e5-download-", dir=destination.parent) as temporary:
            stage = Path(temporary) / "model"
            transferred = _download_set(stage, cancelled, deadline, on_progress)
            _check_active(cancelled, deadline)
            if repair:
                _check_repair_ancestors(destination)
                if (not _publish_repair(stage, destination, cancelled, deadline)
                        and _verified_existing(destination, cancelled, deadline) is None):
                    raise StoryModelInstallError("Repair destination exists but could not be verified; it was not changed",
                                                 "existing_invalid")
            else:
                try:
                    # Concurrent valid installs are reused.
                    stage.rename(destination)
                except OSError:
                    if _verified_existing(destination, cancelled, deadline) is None:
                        raise
            if on_progress is not None:
                on_progress(transferred, transferred)
        return destination
    except StoryModelInstallError:
        raise
    except URLError as error:
        reason = "tls" if isinstance(error.reason, ssl.SSLError) else "network_or_disk"
        raise StoryModelInstallError("Could not reach the model server", reason) from None
    except (OSError, HTTPException, ValueError):
        # Do not include temporary signed CDN URLs, proxies or local user paths.
        raise StoryModelInstallError("Could not download or save the verified model", "network_or_disk") from None
