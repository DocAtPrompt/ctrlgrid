"""Architectural rules that must hold from the first commit.

M1 acceptance criterion 6 (§ 14): the PDF library may appear in exactly one
module. Retrofitting this test later finds nothing, because by then the imports
have already spread — so it exists before the code it guards.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / "ctrlgrid"

# Libraries that belong to exactly one writer and nowhere else (§ 3.3),
# given as paths relative to the package root.
CONFINED = {
    "reportlab": "writers/pdf.py",
    "PIL": "writers/png.py",
    # Not a writer library, but the same rule for the same reason (§ 10.3):
    # font files are read in one place, so a second writer inherits the
    # licence check instead of reimplementing it.
    "fontTools": "fonts.py",
}


def _imported_roots(path: Path) -> set[str]:
    """Top-level module names imported by a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize(("library", "allowed_in"), sorted(CONFINED.items()))
def test_library_confined_to_its_writer(library: str, allowed_in: str) -> None:
    """A generator that imports reportlab kills the second writer before it exists."""
    offenders = [
        path.relative_to(PACKAGE).as_posix()
        for path in sorted(PACKAGE.rglob("*.py"))
        if library in _imported_roots(path)
        and path.relative_to(PACKAGE).as_posix() != allowed_in
    ]
    assert not offenders, (
        f"{library} may only be imported in ctrlgrid/{allowed_in} (§ 3.3), "
        f"but is imported in: {', '.join(offenders)}"
    )


def test_package_imports() -> None:
    import ctrlgrid

    assert ctrlgrid.__version__
