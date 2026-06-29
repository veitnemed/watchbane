import copy
import tempfile
from pathlib import Path

from desktop import watched_view
from posters.cache import poster_identity_key


def test_load_watched_entries_reloads_poster_cache(monkeypatch) -> None:
    movie = {
        "main_info": {"title": "Fresh Show", "user_score": 8.0, "year": 2020},
        "raw_scores": {},
    }
    identity = poster_identity_key("Fresh Show", 2020)
    first_cache = {}
    load_calls = {"count": 0}

    with tempfile.TemporaryDirectory() as temp_root:
        poster_path = Path(temp_root) / "fresh.jpg"
        poster_path.write_bytes(b"poster")
        second_cache = {
            identity: {
                "title": "Fresh Show",
                "year": 2020,
                "status": "found",
                "poster_url": "https://example.com/fresh.jpg",
                "local_path": str(poster_path),
            }
        }

        def fake_load_poster_cache():
            load_calls["count"] += 1
            return copy.deepcopy(first_cache if load_calls["count"] == 1 else second_cache)

        monkeypatch.setattr(watched_view.storage_data, "load_dataset", lambda: {"Fresh Show": movie})
        monkeypatch.setattr("posters.cache.load_poster_cache", fake_load_poster_cache)
        monkeypatch.setattr(
            watched_view,
            "build_export_lookup_cache",
            lambda: {"meta_by_title": {}, "pool_by_identity": {}},
        )

        first_entries = watched_view.load_watched_entries()
        card_before = first_entries[0][2]
        assert card_before.get("poster_src") in (None, "")

        second_entries = watched_view.load_watched_entries()
        card_after = second_entries[0][2]

        assert load_calls["count"] == 2
        assert card_after.get("poster_src") == str(poster_path)
