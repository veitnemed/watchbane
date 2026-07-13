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


def test_status_persists_resolved_not_running_state(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(download_job, "DEFAULT_JOBS_DIR", tmp_path / "jobs")
    paths = download_job.get_job_paths("candidates")
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    paths.status_path.write_text(
        json.dumps(
            {
                "job_name": "candidates",
                "status": "finished",
                "pid": 777,
                "is_running": True,
                "lock_pid": 777,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(download_job, "_is_pid_alive", lambda _pid: False)

    status = download_job.get_status("candidates")
    saved_status = json.loads(paths.status_path.read_text(encoding="utf-8"))

    assert status["status"] == "finished"
    assert status["is_running"] is False
    assert saved_status["is_running"] is False
    assert saved_status["lock_pid"] is None


def test_is_pid_alive_uses_windows_api(monkeypatch) -> None:
    monkeypatch.setattr(download_job.os, "name", "nt")
    monkeypatch.setattr(download_job, "_is_windows_pid_alive", lambda pid: pid == 777)

    assert download_job._is_pid_alive(777) is True
    assert download_job._is_pid_alive(778) is False


def test_release_lock_does_not_remove_another_worker_lock(tmp_path) -> None:
    paths = download_job.get_job_paths("candidates", jobs_root=tmp_path / "jobs")
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    paths.lock_path.write_text(json.dumps({"pid": 222, "job_name": "candidates"}), encoding="utf-8")

    download_job._release_lock(paths, expected_pid=111)

    assert paths.lock_path.is_file()


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


def test_status_write_failure_removes_temporary_file(monkeypatch, tmp_path) -> None:
    import pytest

    target = tmp_path / "status.json"
    monkeypatch.setattr(
        download_job.json,
        "dump",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError, match="disk full"):
        download_job._safe_json_dump(target, {"status": "running"})

    assert target.is_file() is False
    assert target.with_suffix(".tmp").is_file() is False


def test_poster_job_reports_unavailable_storage_without_crashing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(download_job, "DEFAULT_JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(
        download_job,
        "_acquire_lock",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("denied")),
    )

    result = download_job.start_job("candidates")

    assert result == {"ok": False, "error": "storage_unavailable", "status": "failed"}


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


def test_stop_job_uses_status_pid_when_lock_is_stale(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(download_job, "DEFAULT_JOBS_DIR", tmp_path / "jobs")
    paths = download_job.get_job_paths("candidates")
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    paths.lock_path.write_text(json.dumps({"pid": 111, "job_name": "candidates"}), encoding="utf-8")
    paths.status_path.write_text(
        json.dumps({"pid": 222, "job_name": "candidates", "status": "running"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(download_job, "_is_pid_alive", lambda pid: int(pid) == 222)

    result = download_job.stop_job("candidates")

    assert result["ok"] is True
    assert result["pid"] == 222
    assert paths.stop_path.is_file()


def test_run_job_handles_empty_candidate_pool(tmp_path, monkeypatch) -> None:
    from posters import download_job

    monkeypatch.setattr(download_job, "DEFAULT_JOBS_DIR", tmp_path / "jobs")
    paths = download_job.get_job_paths("candidates")
    paths.base_dir.mkdir(parents=True, exist_ok=True)

    def fake_download(
        *,
        progress_callback=None,
        error_callback=None,
        result_callback=None,
        should_stop_callback=None,
    ) -> dict:
        del progress_callback, error_callback, result_callback, should_stop_callback
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
    assert status["is_running"] is False


def test_run_job_writes_progress_to_output_and_finishes_not_running(tmp_path, monkeypatch, capsys) -> None:
    from posters import download_job

    monkeypatch.setattr(download_job, "DEFAULT_JOBS_DIR", tmp_path / "jobs")
    paths = download_job.get_job_paths("candidates")
    paths.base_dir.mkdir(parents=True, exist_ok=True)

    def fake_download(
        *,
        progress_callback=None,
        error_callback=None,
        result_callback=None,
        should_stop_callback=None,
    ) -> dict:
        del error_callback, should_stop_callback
        progress_callback(1, 2, "https://example.com/a.jpg")
        result_callback(1, 2, "https://example.com/a.jpg", "downloaded")
        progress_callback(2, 2, "https://example.com/b.jpg")
        result_callback(2, 2, "https://example.com/b.jpg", "downloaded")
        return {
            "ok": True,
            "is_empty_pool": False,
            "pool_total": 2,
            "download_queue_total": 2,
            "total_urls": 2,
            "downloaded": 2,
            "skipped_existing": 0,
            "failed": 0,
            "skipped_invalid": 0,
            "failures": [],
            "stopped": False,
        }

    monkeypatch.setattr("candidates.service.download_candidate_pool_preview_posters", fake_download)

    result = download_job._run_candidates_job_for_output(paths)

    output = capsys.readouterr().out
    assert result["ok"] is True
    assert "[1/2] https://example.com/a.jpg" in output
    assert "Worker completed: status=finished downloaded=2 skipped_existing=0 failed=0" in output
    status = download_job.get_status("candidates")
    assert status["is_running"] is False
    assert status["processed_urls"] == 2
