"""`pattern.align` (§ 8.5) — which corner the pattern anchors to.

The pattern reflects within its own area so its cycle counts from the chosen
corner: the heavy origin line, and opposite it the incomplete block left by an
uneven fit, both move to that corner. The blade never learns of it (§ 3.3) — the
handle reflects the finished marks on their way to the sheet.
"""

from __future__ import annotations

from pathlib import Path

import pdfread
import pytest

from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter

# 5 mm squared paper with a heavy line first in the cycle, so where the heavy
# lines fall says which corner the pattern anchored to.
DEF = (
    "version: 1\n"
    "page:\n  format: a4\n  margin: 12mm\n"
    "{pattern}"
    "generator: lines\n"
    "families:\n"
    "  - direction: horizontal\n    base_spacing: 5mm\n    base_weight: 0.15pt\n"
    "    weight: [2, 1, 1, 1, 1]\n"
)


def horizontals(path: Path) -> list[tuple[int, bool]]:
    """(y, is_heavy) for every horizontal line, lowest first."""
    lines = [line for line in pdfread.lines_um(path) if line.is_horizontal]
    return sorted((round(line.y1), line.width_mm > 0.1) for line in lines)


def build_to(tmp_path: Path, pattern: str) -> Path:
    path = tmp_path / "grid.pdf"
    build(loads(DEF.format(pattern=pattern), source="test"), PdfWriter(path))
    return path


class TestAlign:
    def test_the_default_anchors_the_heavy_line_at_the_bottom(self, tmp_path: Path) -> None:
        # bottom-left is the coordinate origin (§ 3.5): the cycle counts up from
        # it, so the lowest line is heavy and the incomplete block is at the top.
        lines = horizontals(build_to(tmp_path, ""))
        assert lines[0][1] is True  # the lowest horizontal line is heavy
        assert lines[-1][1] is False  # the topmost is thin (the leftover)

    def test_top_left_moves_the_heavy_line_to_the_top(self, tmp_path: Path) -> None:
        # align: top-left reflects the pattern, so the heavy origin line lands at
        # the top and the incomplete block falls to the bottom. `remainder: end`
        # keeps the grid flush against that top edge.
        lines = horizontals(
            build_to(tmp_path, "pattern:\n  align: top-left\n  remainder: { y: end }\n")
        )
        assert lines[-1][1] is True  # the topmost horizontal line is now heavy
        assert lines[0][1] is False  # the lowest is thin — the incomplete block
        # and it is flush against the pattern top edge (297 - 12 mm margin).
        assert lines[-1][0] == pytest.approx(285_000, abs=100)

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        # § 3.3: reflection is integer arithmetic, so it stays reproducible.
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        pattern = "pattern:\n  align: top-left\n"
        for path in (first, second):
            build(loads(DEF.format(pattern=pattern), source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()
