import copy
import tempfile
from pathlib import Path

from config import constant
from config import scheme
from common import format_score


def _make_movie(title: str, user_score: float, year: int, raw_score: float = 8.0, **extra) -> dict:
    genre_tags = {feature: 0 for feature in constant.GENRE}

    movie = {
        "main_info": {
            "title": title,
            "user_score": user_score,
            "year": year,
        },
        "raw_scores": {
            "kp_score": raw_score,
            "kp_votes": 120000,
            "imdb_score": raw_score,
            "imdb_votes": 1200,
        },
        "computed_scores": format_score.raw_to_struct(
            {
                "kp_score": raw_score,
                "kp_votes": 120000,
                "imdb_score": raw_score,
                "imdb_votes": 1200,
            },
            {
                "title": title,
                "user_score": user_score,
                "year": year,
            },
        ),
        constant.GENRE_SECTION: genre_tags,
    }
    movie.update(extra)
    return movie


def test_build_tmdb_poster_url() -> None:
    from posters.cache import build_tmdb_poster_url

    assert build_tmdb_poster_url("/abc.jpg") == "https://image.tmdb.org/t/p/w342/abc.jpg"
    assert build_tmdb_poster_url("") is None
    assert build_tmdb_poster_url(None) is None


def test_load_poster_cache_missing_file() -> None:
    from posters.cache import load_poster_cache

    with tempfile.TemporaryDirectory() as temp_root:
        assert load_poster_cache(Path(temp_root) / "missing.json") == {}


def test_save_poster_cache_utf8() -> None:
    from posters.cache import save_poster_cache

    with tempfile.TemporaryDirectory() as temp_root:
        path = Path(temp_root) / "posters.json"
        payload = {"бывшие|2020": {"title": "Бывшие", "status": "missing"}}

        save_poster_cache(payload, path=path)
        raw_text = path.read_text(encoding="utf-8")

        assert "Бывшие" in raw_text
        assert "\\u0411" not in raw_text


def test_extract_existing_poster_info_finds_full_url() -> None:
    from posters.cache import extract_existing_poster_info

    movie = _make_movie("Alpha", 8.0, 2020)
    movie["poster_url"] = "https://example.com/poster.jpg"
    original = copy.deepcopy(movie)

    info = extract_existing_poster_info(movie)

    assert movie == original
    assert info["status"] == "found"
    assert info["poster_url"] == "https://example.com/poster.jpg"
    assert info["source"] == "poster_url"


def test_extract_existing_poster_info_builds_url_from_tmdb_path() -> None:
    from posters.cache import extract_existing_poster_info

    movie = _make_movie("Bravo", 8.0, 2019)
    movie["tmdb_data"] = {"poster_path": "/xyz.png"}
    original = copy.deepcopy(movie)

    info = extract_existing_poster_info(movie)

    assert movie == original
    assert info["status"] == "found"
    assert info["poster_path"] == "/xyz.png"
    assert info["poster_url"] == "https://image.tmdb.org/t/p/w342/xyz.png"
    assert info["source"] == "tmdb_data.poster_path"


def test_extract_existing_poster_info_missing() -> None:
    from posters.cache import extract_existing_poster_info

    movie = _make_movie("Charlie", 8.0, 2021)
    original = copy.deepcopy(movie)

    info = extract_existing_poster_info(movie)

    assert movie == original
    assert info["status"] == "missing"
    assert info["poster_url"] is None


def test_build_poster_cache_from_existing_data() -> None:
    from posters.cache import build_poster_cache_from_existing_data, poster_identity_key

    data = {
        "Alpha": _make_movie("Alpha", 8.0, 2020, poster_url="https://example.com/a.jpg"),
        "Bravo": _make_movie("Bravo", 7.0, 2018),
    }
    original = copy.deepcopy(data)

    cache = build_poster_cache_from_existing_data(data)

    assert data == original
    assert cache[poster_identity_key("Alpha", 2020)]["status"] == "found"
    assert cache[poster_identity_key("Bravo", 2018)]["status"] == "missing"
    assert cache[poster_identity_key("Alpha", 2020)]["poster_url"] == "https://example.com/a.jpg"


def test_build_watched_movie_card_uses_poster_cache() -> None:
    from posters.cache import load_poster_cache, poster_identity_key, save_poster_cache
    from web.export import build_watched_movie_card

    with tempfile.TemporaryDirectory() as temp_root:
        cache_path = Path(temp_root) / "posters.json"
        save_poster_cache(
            {
                poster_identity_key("Cached Movie", 2022): {
                    "title": "Cached Movie",
                    "year": 2022,
                    "source": "poster_cache",
                    "poster_path": "/cached.jpg",
                    "poster_url": "https://image.tmdb.org/t/p/w342/cached.jpg",
                    "local_path": None,
                    "status": "found",
                    "updated_at": "2026-06-24T00:00:00+00:00",
                }
            },
            path=cache_path,
        )

        movie = _make_movie("Cached Movie", 8.0, 2022)
        card = build_watched_movie_card(movie, poster_cache=load_poster_cache(cache_path))

        assert card["poster_url"] == "https://image.tmdb.org/t/p/w342/cached.jpg"
        assert card["poster_src"] == "https://image.tmdb.org/t/p/w342/cached.jpg"
        assert card["poster_source"] == "poster_cache"


def test_build_poster_cache_from_existing_data_links_local_image_file(monkeypatch) -> None:
    import tempfile

    from posters.cache import build_poster_cache_from_existing_data, poster_identity_key
    from posters.download_images import poster_image_path_for_identity

    with tempfile.TemporaryDirectory() as temp_root:
        temp_dir = Path(temp_root)
        monkeypatch.setattr("posters.download_images.DEFAULT_POSTER_IMAGES_DIR", temp_dir)

        data = {"Alpha": _make_movie("Alpha", 8.0, 2020)}
        identity = poster_identity_key("Alpha", 2020)
        image_path = poster_image_path_for_identity(identity)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"poster")

        cache = build_poster_cache_from_existing_data(data)

        assert cache[identity]["local_path"] == str(image_path)
        assert cache[identity]["status"] == "found"


def test_build_watched_movie_card_falls_back_to_default_local_image(monkeypatch) -> None:
    import tempfile

    from posters.cache import poster_identity_key
    from posters.download_images import poster_image_path_for_identity
    from web.export import build_watched_movie_card

    with tempfile.TemporaryDirectory() as temp_root:
        temp_dir = Path(temp_root)
        monkeypatch.setattr("posters.download_images.DEFAULT_POSTER_IMAGES_DIR", temp_dir)

        movie = _make_movie("Fallback Movie", 8.0, 2021)
        identity = poster_identity_key("Fallback Movie", 2021)
        image_path = poster_image_path_for_identity(identity)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"poster")

        card = build_watched_movie_card(movie, poster_cache={})

        assert card["poster_src"] == str(image_path)
