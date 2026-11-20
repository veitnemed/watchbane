"""Run isolated Linux-offscreen-capable story-search and Collection smoke checks.

The operator provides the catalogue, verified local E5 directory, query and
expected top title. Nothing is downloaded. The optional screenshots may contain
the operator's input/results and are always local; the report contains no titles,
queries, paths, catalogue rows or synopses.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stdout
import json
import os
from pathlib import Path
from shutil import copyfile
import subprocess
import sys
import tempfile
from time import monotonic, sleep
import unicodedata
from unittest.mock import patch

from tools.qa.isolation import IsolationError, assert_runtime_is_isolated

MODULE = "tools.qa.smoke_story_desktop"
PROFILE_MARKER = ".watchbane_story_smoke"
PROFILE_KEYS = ("WATCHBANE_", "TMDB_", "KINOPOISK_", "KP_API_")


class SmokeFailure(RuntimeError):
    """A fixed, operator-safe failure reason."""


def check(condition, failure):
    if not condition:
        raise SmokeFailure(failure)


def match_title(actual, expected):
    def normalized(value):
        return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()

    return normalized(actual) == normalized(expected)


def _clean_environment(platform):
    values = {name: value for name, value in os.environ.items()
              if not name.upper().startswith(PROFILE_KEYS)
              and name not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"}}
    if platform:
        values["QT_QPA_PLATFORM"] = platform
    return values


def _fresh_directory(path, *, label):
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise SmokeFailure(f"{label} must be a fresh or empty directory.")
    return path


def _child_run(phase, payload, *, timeout, platform):
    # Do not expose the query, title or operator file paths as child CLI flags.
    try:
        result = subprocess.run(
            [sys.executable, "-m", MODULE, f"_child_{phase}"],
            cwd=Path(__file__).resolve().parents[2],
            input=json.dumps(payload, ensure_ascii=True).encode("ascii"),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=_clean_environment(platform), timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise SmokeFailure(f"{phase}: subprocess timed out.") from exc
    try:
        report = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise SmokeFailure(f"{phase}: Qt subprocess did not return a report.") from exc
    if result.returncode or not report.get("ok"):
        raise SmokeFailure(f"{phase}: {report.get('failure', 'desktop subprocess failed')}")
    return report


def _isolated_install_destination(story, profile):
    from candidates.story_model_install import profile_story_model_destination
    from config import constant

    root = Path(story._model_install_profile).resolve()
    check(root == Path(constant.APP_DATA_DIR).resolve() and root.is_relative_to(profile),
          "Installer did not bind to the isolated active data profile.")
    destination = profile_story_model_destination(root)
    check(destination.resolve().is_relative_to(profile), "Model cache is outside the isolated profile.")
    return destination


def _prepare_pinned_cache(destination, source):
    from candidates.story_model_manifest import PORTABLE_FILES

    for name in PORTABLE_FILES:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        check(not target.exists() and not target.is_symlink(), "Model cache is not empty.")
        try:
            os.link(source / name, target)
        except OSError:
            try:
                copyfile(source / name, target)
            except OSError:
                raise SmokeFailure("Could not populate the disposable model cache.") from None


def _desktop_phase(phase, options):
    # Establish the profile before product modules resolve their paths.
    from tools.qa.isolation import apply_isolated_data_dir
    profile = assert_runtime_is_isolated(options["profile"])
    check((profile / PROFILE_MARKER).is_file(), "Profile is not reserved as a disposable smoke directory.")
    apply_isolated_data_dir(profile)
    verify_cached_install = options.get("verify_cached_install", False)
    if not verify_cached_install:
        os.environ["WATCHBANE_STORY_MODEL_DIR"] = options["model_dir"]
    os.environ["WATCHBANE_INTERFACE_LANGUAGE"] = "ru"
    os.environ["WATCHBANE_DATA_LANGUAGE"] = "ru"

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    from PyQt6.QtNetwork import QNetworkAccessManager
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QFileDialog, QFrame, QLabel, QPushButton, QScrollArea
    import requests
    import socket

    network_attempts = []

    def deny_network(*_args, **_kwargs):
        network_attempts.append(True)
        raise SmokeFailure("Unexpected networking attempted; blocked before transmission.")

    def quiet_poster(*_args, **_kwargs):
        # Posters are optional online UI, not part of this strictly offline run.
        return None

    def wait_until(condition, failure):
        end = monotonic() + options["step_timeout"]
        while not condition():
            app.processEvents()
            if monotonic() >= end:
                raise SmokeFailure(failure)
            sleep(.01)
        app.processEvents()

    def screenshot(name, widget=None):
        if options["output_dir"]:
            file = Path(options["output_dir"]) / f"{phase}-{name}.png"
            check((window if widget is None else widget).grab().save(str(file)), "Could not save requested screenshot.")

    with ExitStack() as guards:
        for owner, attribute in (
            (requests.sessions.Session, "request"), (socket.socket, "connect"),
            (socket.socket, "connect_ex"), (socket, "getaddrinfo"),
            *[(QNetworkAccessManager, method) for method in
              ("get", "post", "put", "head", "deleteResource", "sendCustomRequest")],
        ):
            guards.enter_context(patch.object(owner, attribute, deny_network))
        from desktop.shared.story_posters import DirectPosterController
        from desktop.shell.main_window import WatchedMoviesWindow
        from desktop.theme import FONT_APP, FONT_FAMILY
        from desktop.theme.scaling import font_px, set_ui_scale
        from storage.runtime import ensure_runtime_data_layout
        guards.enter_context(patch.object(DirectPosterController, "enqueue", quiet_poster))
        ensure_runtime_data_layout()
        app = QApplication([])
        set_ui_scale(options["scale"])
        app.setFont(QFont(FONT_FAMILY, font_px(FONT_APP)))
        window = WatchedMoviesWindow(initial_size=(1280, 900))
        started = monotonic()
        window.show()
        window.schedule_tmdb_startup_gate(0)
        app.processEvents()
        elapsed = {}
        try:
            registry = window._tab_registry
            story = registry._specs["story"].view
            collection = registry._specs["watched"].view
            check(window.isVisible() and window._main_tabs.count() == 2, "Expected two-section desktop shell.")
            check(window._main_tabs.currentWidget() is story.widget, "Did not open on the search home.")
            check(not window._tmdb_gate_timer.isActive(), "Unexpected TMDb activation gate.")
            check(not story.seed_path and not story._catalog_ready
                  and not story._records and story.cards_layout.count() == 1,
                  "Search home is not clean or generated unrelated titles.")
            check(story.catalog_button.isVisible() and story.snapshot_button.isVisible(),
                  "Expected both catalogue entry points on the clean search home.")
            if phase == "first":
                check(not collection._entries, "Fresh profile already contains saved titles.")
                screenshot("empty")
                if verify_cached_install:
                    destination = _isolated_install_destination(story, profile)
                    _prepare_pinned_cache(destination, Path(options["model_dir"]))
                    check(story.model_dir is None and story.install_model_button.isVisible(),
                          "Expected the model to be unconfigured on fresh startup.")
                    QTest.mouseClick(story.install_model_button, Qt.MouseButton.LeftButton)
                    app.processEvents()
                    check(story._install_confirm.isEnabled(), "Model install button was unavailable.")
                    began = monotonic()
                    QTest.mouseClick(story._install_confirm, Qt.MouseButton.LeftButton)
                    wait_until(lambda: story._model_install_worker is None, "Cached model verification timed out.")
                    check(story.model_dir == str(destination) and story._model_preference.read() == str(destination),
                          "Model verification or preference persistence failed.")
                    elapsed["install_cached_verification_ms"] = round((monotonic() - began) * 1000)
                    screenshot("installed", story._model_install_dialog)
                    story._model_install_dialog.accept()
                with patch.object(QFileDialog, "getOpenFileName", return_value=(options["catalog"], "")):
                    began = monotonic()
                    QTest.mouseClick(story.snapshot_button, Qt.MouseButton.LeftButton)
                    wait_until(lambda: story._snapshot_worker is None, "Catalogue file validation timed out.")
                    elapsed["file_validation_ms"] = round((monotonic() - began) * 1000)
                check(story.seed_path == options["catalog"] and story._snapshot_rows > 0
                      and story._worker is None and story.catalog_status.text().startswith("Только каталог из файла"),
                      "The local file chooser did not establish a file-only scope.")
                check(not story.catalog_button.isVisible(), "TMDb is still active while file-only search is selected.")
                story.query.setText(options["query"])
                began = monotonic()
                QTest.keyClick(story.query, Qt.Key.Key_Return)
                wait_until(lambda: story._worker is None, "E5 search timed out.")
                elapsed["search_ms"] = round((monotonic() - began) * 1000)
                check("E5" in story.backend_label.text(), "The search did not complete in E5 mode.")
                check(story.cards_layout.count() > 1, "Search returned no cards.")
                top = story.cards_layout.itemAt(0).widget()
                check(isinstance(top, QFrame), "Top render is not a story card.")
                title = top.findChild(QLabel, "storyTitle")
                check(title is not None and match_title(title.text(), options["expected_title"]),
                      "Top result did not match the operator's expectation.")
                save = top.findChild(QPushButton, "storySaveAction")
                check(save is not None and save.isEnabled(), "Top result is not available to save.")
                results_scroll = story.widget.findChild(QScrollArea)
                check(results_scroll is not None, "Search results have no keyboard-scrollable area.")
                results_scroll.ensureWidgetVisible(save)
                QTest.mouseClick(save, Qt.MouseButton.LeftButton)
                check(not save.isEnabled() and save.text() == "В коллекции",
                      "Save action did not confirm persistence.")
                screenshot("result")
            if phase == "reopen" and verify_cached_install:
                check(story.model_dir == str(_isolated_install_destination(story, profile)),
                      "Installed model did not remain configured after restart.")
            registry.focus("watched")
            app.processEvents()
            rows = collection.cards.findChildren(QLabel, "storyTitle")
            check(len(rows) == 1 and match_title(rows[0].text(), options["expected_title"]),
                  "Saved result is missing or mixed with other Collection results.")
            check(not bool(network_attempts), "Unexpected networking attempted; blocked before transmission.")
            screenshot("collection")
        finally:
            window.shutdown_background_workers()
            window.close()
            app.processEvents()
        check(not network_attempts, "Unexpected networking attempted during cleanup; blocked.")
        return {"ok": True, "pid": os.getpid(), "qt_platform": app.platformName(),
                "elapsed_ms": round((monotonic() - started) * 1000),
                "unexpected_network_calls": len(network_attempts), **elapsed}


def _child(phase):
    try:
        opts = json.load(sys.stdin)
        # Qt diagnostics and dependency output are not part of the
        # machine-readable report and may contain operator-private names.
        with redirect_stdout(sys.stderr):
            report = _desktop_phase(phase, opts)
    except SmokeFailure as exc:
        report = {"ok": False, "failure": str(exc)}
    except Exception as exc:
        report = {"ok": False, "failure": f"Unexpected {type(exc).__name__}."}
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["ok"] else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv in (["_child_first"], ["_child_reopen"]):
        return _child(argv[0].removeprefix("_child_"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True, help="Existing local Watchbane JSONL snapshot")
    parser.add_argument("--model-dir", type=Path, required=True, help="Existing verified multilingual-e5-small directory")
    parser.add_argument("--verify-cached-install", action="store_true",
                        help="Exercise the real in-app installer and preference using a prefilled disposable cache; "
                             "does not verify downloading")
    parser.add_argument("--query", required=True)
    parser.add_argument("--expected-title", required=True, help="Displayed title expected in first result")
    parser.add_argument("--profile", type=Path, help="New/empty disposable profile (temporary if omitted)")
    parser.add_argument("--output-dir", type=Path, help="New/empty folder for optional private PNG screenshots")
    parser.add_argument("--scale", type=float, choices=(1.0, 1.25), default=1.0)
    parser.add_argument("--step-timeout", type=float, default=120, help="Seconds allowed per background step")
    parser.add_argument("--qt-platform", default="offscreen" if sys.platform.startswith("linux") else None)
    args = parser.parse_args(argv)
    try:
        catalog = args.catalog.expanduser().resolve()
        directory = args.model_dir.expanduser().resolve()
        check(catalog.is_file() and catalog.suffix.casefold() == ".jsonl", "An existing JSONL catalogue is required.")
        check(directory.is_dir(), "An existing model directory is required.")
        check(0 < len(args.query.strip()) <= 600 and bool(args.expected_title.strip()), "Query or expected title is empty/invalid.")
        check(0 < args.step_timeout <= 1800, "Step timeout must be between 0 and 1800 seconds.")
        with ExitStack() as stack:
            if args.profile:
                profile = _fresh_directory(assert_runtime_is_isolated(args.profile), label="Profile")
            else:
                profile = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="watchbane-story-smoke-")))
            output = (assert_runtime_is_isolated(args.output_dir) if args.output_dir else None)
            if output is not None:
                _fresh_directory(output, label="Screenshot output")
                check(output != profile and not output.is_relative_to(profile) and not profile.is_relative_to(output),
                      "Profile and screenshot output must be separate directories.")
                output.mkdir(parents=True, exist_ok=True)
            # Reserve the passed profile only after all checks. A simultaneous
            # use must not run a second writer into it.
            profile.mkdir(parents=True, exist_ok=True)
            with (profile / PROFILE_MARKER).open("x", encoding="ascii") as marker:
                marker.write("isolated disposable profile\n")
            payload = {"catalog": str(catalog), "model_dir": str(directory), "profile": str(profile),
                       "query": args.query, "expected_title": args.expected_title,
                       "output_dir": str(output) if output is not None else None,
                       "step_timeout": args.step_timeout, "scale": args.scale,
                       "verify_cached_install": args.verify_cached_install}
            first = _child_run("first", payload, timeout=args.step_timeout * 2 + 30, platform=args.qt_platform)
            reopen = _child_run("reopen", payload, timeout=args.step_timeout + 30, platform=args.qt_platform)
            check(first["pid"] != reopen["pid"], "Expected independent first and reopen Qt processes.")
    except (SmokeFailure, ValueError, OSError) as exc:
        if isinstance(exc, IsolationError):
            message = "Profile or screenshot output is not isolated from the real Watchbane runtime."
        else:
            message = str(exc) if isinstance(exc, SmokeFailure) else type(exc).__name__
        print(f"Desktop smoke failed: {message}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "isolated_processes": 2, "catalogue_chooser": True,
                      "e5_top_result_matches": True, "reopened_collection_matches": True,
                      "poster_network_disabled": True,
                      "cached_model_verified_in_ui": args.verify_cached_install, "first": first, "reopen": reopen}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
