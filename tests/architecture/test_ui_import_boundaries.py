"""Architecture guard: desktop code stays above infrastructure details."""

from __future__ import annotations

import ast
from pathlib import Path


FORBIDDEN_UI_IMPORTS = (
    "storage.sqlite",
    "candidates.repositories",
    "candidates.sources.tmdb.builder",
    "apis.tmdb_api",
)


def _imported_modules(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_desktop_does_not_import_infrastructure_implementation_modules() -> None:
    desktop_root = Path(__file__).resolve().parents[2] / "desktop"
    violations: list[str] = []
    for source_path in desktop_root.rglob("*.py"):
        for module in _imported_modules(source_path):
            if any(module == forbidden or module.startswith(f"{forbidden}.") for forbidden in FORBIDDEN_UI_IMPORTS):
                violations.append(f"{source_path.relative_to(desktop_root)}: {module}")
    assert violations == [], "Desktop imports must go through services or app.use_cases:\n" + "\n".join(violations)
