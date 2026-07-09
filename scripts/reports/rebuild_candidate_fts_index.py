"""Rebuild candidate FTS index from the current SQLite pool."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from candidates.search.fts_index import rebuild_fts_index_timed  # noqa: E402
from storage.sqlite.connection import connect  # noqa: E402
from storage.sqlite.migrations import get_current_schema_version  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild candidate FTS5 index.")
    parser.parse_args(argv)

    conn = connect()
    try:
        schema_version = get_current_schema_version(conn)
        stats = rebuild_fts_index_timed(conn)
        conn.commit()
    finally:
        conn.close()

    payload = {
        "schema_version": schema_version,
        "count": stats["count"],
        "elapsed_ms": stats["elapsed_ms"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
