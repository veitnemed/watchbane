import json

from pathlib import Path

from posters import download_job


def test_start_candidates_job_refuses_second_start_when_lock_is_active(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(download_job, "DEFAULT_JOBS_DIR", tmp_path / "jobs")
    paths = download_job.get_job_paths("candidates")
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    paths.lock_path.write_text(json.dumps({"pid": 777, "job_name": "candidates"}), encoding="utf-8")

    monkeypatch.setattr(download_job, "_is_pid_alive", lambda _pid: True)
    def fail_start(*_args, **_kwargs):
        raise AssertionError("subprocess should not be started when job is active")

    monkeypatch.setattr(download_job.subprocess, "Popen", fail_start)

    result = download_job.start_job("candidates")

    assert result["ok"] is False
    assert result["already_running"] is True


def test_start_candidates_job_refuses_second_start_when_status_pid_is_active(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(download_job, "DEFAULT_JOBS_DIR", tmp_path / "jobs")
    paths = download_job.get_job_paths("candidates")
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    paths.status_path.write_text(
        json.dumps({"pid": 888, "job_name": "candidates", "status": "running"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(download_job, "_is_pid_alive", lambda pid: int(pid) == 888)

    def fail_start(*_args, **_kwargs):
        raise AssertionError("subprocess should not be started when status pid is active")

    monkeypatch.setattr(download_job.subprocess, "Popen", fail_start)

    result = download_job.start_job("candidates")

    assert result["ok"] is False
    assert result["already_running"] is True
    assert result["pid"] == 888


def test_status_reads_json_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(download_job, "DEFAULT_JOBS_DIR", tmp_path / "jobs")
    paths = download_job.get_job_paths("candidates")
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    status_path = paths.status_path
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(
            {
                "job_name": "candidates",
                "status": "finished",
                "is_running": False,
                "processed_urls": 2,
                "total_urls": 5,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    status = download_job.get_status("candidates")

    assert status["status"] == "finished"
    assert status["processed_urls"] == 2
    assert status["total_urls"] == 5


def test_background_process_is_detached_from_console(tmp_path) -> None:
    log_path = tmp_path / "worker.log"
    with open(log_path, "w", encoding="utf-8") as log_file:
        kwargs = download_job._background_process_kwargs(log_file)

    assert kwargs["stdin"] is download_job.subprocess.DEVNULL
    assert kwargs["stderr"] is download_job.subprocess.STDOUT
    assert kwargs["close_fds"] is True
    if download_job.os.name == "nt":
        assert kwargs["creationflags"] & download_job.subprocess.CREATE_NEW_PROCESS_GROUP
        assert kwargs["creationflags"] & download_job.subprocess.CREATE_NO_WINDOW


def test_download_preview_posters_stops_between_urls(monkeypatch, tmp_path) -> None:
    from posters import download_images

    preview_dir = tmp_path / "preview"
    monkeypatch.setattr(download_images, "PREVIEW_POSTER_DIR", preview_dir)
    monkeypatch.setattr(download_images.time, "sleep", lambda *_args, **_kwargs: None)

    state = {"attempts": 0}

    def should_stop() -> bool:
        return state["attempts"] >= 2

    def fake_download(url: str, _destination) -> tuple[bool, str]:
        state["attempts"] += 1
        return True, "downloaded"

    monkeypatch.setattr(download_images, "_download_preview_poster", fake_download)

    stats = download_images.download_preview_posters_for_urls(
        ["https://example.com/a.jpg", "https://example.com/b.jpg", "https://example.com/c.jpg"],
        should_stop_callback=should_stop,
    )

    assert stats["stopped"] is True
    assert state["attempts"] == 2


def test_stop_job_writes_stop_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(download_job, "DEFAULT_JOBS_DIR", tmp_path / "jobs")
    paths = download_job.get_job_paths("candidates")
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    paths.lock_path.write_text(json.dumps({"pid": 777, "job_name": "candidates"}), encoding="utf-8")

    monkeypatch.setattr(download_job, "_is_pid_alive", lambda _pid: True)

    result = download_job.stop_job("candidates")

    assert result["ok"] is True
    assert paths.stop_path.is_file()


def test_run_job_handles_empty_candidate_pool(tmp_path, monkeypatch) -> None:
    from posters import download_job

    monkeypatch.setattr(download_job, "DEFAULT_JOBS_DIR", tmp_path / "jobs")
    paths = download_job.get_job_paths("candidates")
    paths.base_dir.mkdir(parents=True, exist_ok=True)

    def fake_download(*, progress_callback=None, error_callback=None, should_stop_callback=None) -> dict:
        del progress_callback, error_callback, should_stop_callback
        return {
            "ok": True,
            "is_empty_pool": True,
            "pool_total": 0,
            "unique_urls": 0,
            "poster_displayable": 0,
            "poster_metadata_only": 0,
            "poster_missing": 0,
            "download_queue_total": 0,
            "already_displayable": 0,
            "total_urls": 0,
            "downloaded": 0,
            "skipped_existing": 0,
            "failed": 0,
            "skipped_invalid": 0,
            "failures": [],
            "stopped": False,
        }

    monkeypatch.setattr("candidates.service.download_candidate_pool_preview_posters", fake_download)

    result = download_job._run_candidates_job_for_output(paths)

    assert result["ok"] is True
    status = download_job.get_status("candidates")
    assert status["is_empty_pool"] is True
    assert status["status"] == "finished"
