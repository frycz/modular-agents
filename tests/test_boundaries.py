"""The library must not depend on the examples: interfaces/ and composites/ import only themselves, the standard library and httpx."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

LIBRARY = Path(__file__).parent.parent / "src" / "modular_agents"
ALLOWED = set(sys.stdlib_module_names) | {"modular_agents", "httpx"}


def imported_modules(path: Path) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("path", sorted(LIBRARY.rglob("*.py")), ids=lambda p: str(p.relative_to(LIBRARY)))
def test_library_imports_only_itself_stdlib_and_httpx(path):
    assert {m for m in imported_modules(path) if m.split(".")[0] not in ALLOWED} == set()


@pytest.mark.parametrize("path", sorted((LIBRARY / "interfaces").rglob("*.py")), ids=lambda p: p.name)
def test_interfaces_do_not_import_composites(path):
    assert {m for m in imported_modules(path) if m.startswith("modular_agents.composites")} == set()
