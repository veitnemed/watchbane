"""Deprecated shim for legacy JSON import utilities.

Use `storage.legacy_json.importer` instead.
"""

from storage.legacy_json.importer import (  # noqa: F401
    LegacyJsonPaths,
    backup_legacy_json,
    import_legacy_json_to_sqlite,
    legacy_paths,
    load_legacy_json_mapping,
)
