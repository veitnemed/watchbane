"""CI wrapper around the unchanged verified story installer (no raw diagnostics)."""
from argparse import ArgumentParser
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic

from candidates.story_model_install import (
    DOWNLOAD_BYTE_LIMIT,
    StoryModelInstallError,
    install_story_model,
)


_KNOWN_CODES = frozenset({
    "cancelled", "timeout", "idle_timeout", "redirect_host", "http_status",
    "invalid_response", "integrity", "existing_invalid", "tls", "network_or_disk",
})
_MAX_HEARTBEATS = 18
_HEARTBEAT_SECONDS = 30


def run_install(destination: Path, *, heartbeat_seconds=_HEARTBEAT_SECONDS) -> int:
    started = monotonic()
    stop, state_lock = Event(), Lock()
    seen = 0

    def log(phase, error=None):
        with state_lock:
            suffix = f" error={error}" if error is not None else ""
            print(f"e5_install phase={phase} elapsed_s={int(monotonic() - started)} observed_bytes={seen}{suffix}",
                  flush=True)

    def progress(received, _total):
        nonlocal seen
        if type(received) is not int or not 0 < received <= DOWNLOAD_BYTE_LIMIT:
            return
        with state_lock:
            first = seen == 0
            seen = max(seen, received)
        if first:
            log("first_progress")

    def heartbeat():
        for _ in range(_MAX_HEARTBEATS):
            if stop.wait(heartbeat_seconds):
                return
            log("install_in_progress")

    log("installer_started")
    monitor = Thread(target=heartbeat, daemon=True)
    monitor.start()
    try:
        install_story_model(destination, on_progress=progress)
    except StoryModelInstallError as error:
        code = error.code if type(error.code) is str and error.code in _KNOWN_CODES else "installer_error"
    except Exception:
        code = "unexpected_error"
    else:
        code = None
    finally:
        stop.set()
        monitor.join()
    if code is None:
        log("verified")
        return 0
    log("failed", code)
    return 1


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    return run_install(args.destination)


if __name__ == "__main__":
    raise SystemExit(main())
