import copy
from pathlib import Path
from unittest.mock import patch

from common import format_score
from config import constant
from config import scheme


def _make_movie(title: str, user_score: float, year: int, poster_url: str | None = None) -> dict:
    raw_scores = {
        "kp_score": 8.0,
        "kp_votes": 120000,
        "imdb_score": 8.0,
        "imdb_votes": 1200,
    }
    main_info = {
        "title": title,
        "user_score": user_score,
        "year": year,
    }
    movie = {
        "main_info": main_info,
        "raw_scores": raw_scores,
        "computed_scores": format_score.raw_to_struct(raw_scores, main_info),
        scheme.TAGS_VIBE: {feature: 0 for feature in constant.TAGS_VIBE},
        constant.GENRE_SECTION: {feature: 0 for feature in constant.GENRE},
    }
    if poster_url is not None:
        movie["poster_url"] = poster_url
    return movie


def test_download_poster_for_title_downloads_and_persists_local_path(monkeypatch) -> None:
    from posters.cache import poster_identity_key
    from posters.download_images import download_poster_for_title

    identity = poster_identity_key("Alpha", 2020)
    cache = {
        identity: {
            "title": "Alpha",
            "year": 2020,
            "status": "found",
            "poster_url": "https://example.com/a.jpg",
        }
    }

    def fake_download(url: str, destination: Path) -> bool:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"poster")
        return True

    saved: dict = {}

    monkeypatch.setattr("posters.download_images._download_poster", fake_download)
    monkeypatch.setattr("posters.download_images.save_poster_cache", lambda payload: saved.update(payload))

    with patch("posters.download_images.load_poster_cache", return_value=copy.deepcopy(cache)):
        result = download_poster_for_title("Alpha", 2020)

    assert result["ok"] is True
    assert result["reason"] == "downloaded"
    assert result["local_path"] is not None
    assert Path(result["local_path"]).is_file()
    assert saved[identity]["local_path"] == result["local_path"]


def test_download_poster_for_title_skips_existing_file(monkeypatch) -> None:
    import tempfile

    from posters.cache import poster_identity_key
    from posters.download_images import download_poster_for_title, poster_image_path_for_identity

    with tempfile.TemporaryDirectory() as temp_root:
        temp_dir = Path(temp_root)
        identity = poster_identity_key("Alpha", 2020)
        monkeypatch.setattr("posters.download_images.DEFAULT_POSTER_IMAGES_DIR", temp_dir)
        image_path = poster_image_path_for_identity(identity)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"existing")

        cache = {
            identity: {
                "title": "Alpha",
                "year": 2020,
                "status": "found",
                "poster_url": "https://example.com/a.jpg",
            }
        }

        download_calls: list[str] = []

        def fake_download(url: str, destination: Path) -> bool:
            download_calls.append(url)
            return True

        monkeypatch.setattr("posters.download_images._download_poster", fake_download)

        with patch("posters.download_images.load_poster_cache", return_value=copy.deepcopy(cache)):
            with patch("posters.download_images.save_poster_cache") as save_mock:
                result = download_poster_for_title("Alpha", 2020)

        assert result["ok"] is True
        assert result["reason"] == "skipped_existing"
        assert result["local_path"] == str(image_path)
        assert download_calls == []
        save_mock.assert_called_once()


def test_remove_local_poster_file_deletes_local_path() -> None:
    import tempfile

    from posters.download_images import remove_local_poster_file

    with tempfile.TemporaryDirectory() as temp_root:
        poster_path = Path(temp_root) / "alpha.jpg"
        poster_path.write_bytes(b"x")

        result = remove_local_poster_file(
            "Alpha",
            2020,
            cache_entry={"local_path": str(poster_path)},
        )

    assert result["deleted"] is True
    assert poster_path.is_file() is False


def test_add_dataset_record_downloads_poster_after_cache_sync(monkeypatch) -> None:
    from dataset import dataset_records

    movie = _make_movie("New Show", 8.5, 2021, poster_url="https://example.com/new.jpg")
    download_calls: list[tuple[str, object]] = []

    def fake_sync(title, year, meta_obj=None, movie=None, extra_sources=None, cache=None, persist=True):
        return {"status": "found", "poster_url": "https://example.com/new.jpg"}

    def fake_download(title, year, *, cache=None):
        download_calls.append((title, year))
        return {"ok": True, "reason": "downloaded", "local_path": "C:/cache/new.jpg"}

    with patch.object(dataset_records, "load_dataset", return_value={}):
        with patch.object(dataset_records, "save_dataset"):
            with patch.object(dataset_records, "add_movies_to_meta", return_value=True):
                with patch.object(dataset_records, "get_meta_obj", return_value=None):
                    with patch("posters.cache.sync_poster_cache_from_meta_and_sources", side_effect=fake_sync):
                        with patch("posters.download_images.download_poster_for_title", side_effect=fake_download):
                            result = dataset_records.add_dataset_record(movie)

    assert result.ok is True
    assert download_calls == [("New Show", 2021)]


def test_add_dataset_record_downloads_poster_from_hints_when_cache_missing(monkeypatch) -> None:
    from dataset import dataset_records

    movie = _make_movie("Hint Show", 8.0, 2022)
    poster_hints = {
        "status": "found",
        "poster_url": "https://example.com/hint.jpg",
        "source": "tmdb_data.poster_path",
    }
    upsert_calls: list[tuple] = []
    download_calls: list[tuple] = []

    def fake_sync(title, year, meta_obj=None, movie=None, extra_sources=None, cache=None, persist=True):
        return {"status": "missing", "poster_url": None}

    def fake_upsert(title, year, poster_info, cache=None, persist=True):
        upsert_calls.append((title, year, poster_info))
        return {"status": "found", "poster_url": poster_info.get("poster_url")}

    def fake_download(title, year, *, cache=None):
        download_calls.append((title, year))
        if len(download_calls) == 1:
            return {"ok": False, "reason": "missing_cache", "local_path": None}
        return {"ok": True, "reason": "downloaded", "local_path": "C:/cache/hint.jpg"}

    with patch.object(dataset_records, "load_dataset", return_value={}):
        with patch.object(dataset_records, "save_dataset"):
            with patch.object(dataset_records, "add_movies_to_meta", return_value=True):
                with patch.object(dataset_records, "get_meta_obj", return_value=None):
                    with patch("posters.cache.sync_poster_cache_from_meta_and_sources", side_effect=fake_sync):
                        with patch("posters.cache.upsert_poster_cache_entry", side_effect=fake_upsert):
                            with patch("posters.download_images.download_poster_for_title", side_effect=fake_download):
                                result = dataset_records.add_dataset_record(
                                    movie,
                                    poster_hints=poster_hints,
                                )

    assert result.ok is True
    assert len(download_calls) == 2
    assert upsert_calls == [("Hint Show", 2022, poster_hints)]


def test_delete_watched_record_removes_local_poster_file(monkeypatch) -> None:
    import tempfile

    from dataset import delete_record as module
    from posters.cache import poster_identity_key

    with tempfile.TemporaryDirectory() as temp_root:
        poster_path = Path(temp_root) / "alpha.jpg"
        poster_path.write_bytes(b"x")
        identity = poster_identity_key("Alpha", 2020)
        poster_cache = {
            identity: {
                "title": "Alpha",
                "year": 2020,
                "status": "found",
                "poster_url": "https://example.com/a.jpg",
                "local_path": str(poster_path),
            }
        }

        dataset = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
        saved_cache: dict = {}

        monkeypatch.setattr(module.storage_data, "load_dataset", lambda: copy.deepcopy(dataset))
        monkeypatch.setattr(module.storage_data, "load_meta", lambda: {})
        monkeypatch.setattr(module.storage_data, "save_dataset", lambda payload: None)
        monkeypatch.setattr(module.storage_data, "save_meta", lambda payload: None)
        monkeypatch.setattr(module, "load_poster_cache", lambda: copy.deepcopy(poster_cache))
        monkeypatch.setattr(module, "save_poster_cache", lambda payload: saved_cache.update(payload))
        monkeypatch.setattr(module, "backup_before_watched_delete", lambda timestamp=None: [])

        result = module.delete_watched_record("Alpha", timestamp="test")

    assert result["ok"] is True
    assert result["deleted_poster_file"] == 1
    assert poster_path.is_file() is False
    assert identity not in saved_cache
