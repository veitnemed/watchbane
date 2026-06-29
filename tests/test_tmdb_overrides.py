import json
import tempfile
from pathlib import Path

from candidates.keys import title_identity_key
from posters.tmdb_overrides import (
    get_watched_tmdb_override,
    load_watched_tmdb_overrides,
)


def test_load_watched_tmdb_overrides_missing_file() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        missing = Path(tmp_dir) / "missing.json"
        assert load_watched_tmdb_overrides(missing) == {}


def test_load_watched_tmdb_overrides_reads_json() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "overrides.json"
        payload = {
            "alpha|2020": {
                "tmdb_id": 123,
                "media_type": "tv",
            }
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        loaded = load_watched_tmdb_overrides(path)

        assert loaded == payload
        assert get_watched_tmdb_override("Alpha", 2020, overrides=loaded)["tmdb_id"] == 123
        assert title_identity_key({"title": "Alpha", "year": 2020}) == "alpha|2020"
