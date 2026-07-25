"""A slanted family, measured out of a finished PDF (§ 7.1, § 8.2).

The promise for a slanted family is that `base_spacing` is the *perpendicular*
distance between neighbours — not the distance along an axis, which is what a
naive implementation produces and what no unit test comparing the code to
itself would catch. So it is measured here out of the written file.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter
from tests.pdfread import lines_um

ANGLE = 55.0
SPACING = 8000  # µm

SLANTED = (
    "version: 1\n"
    "page:\n  format: a4\n  margin: 20mm\n"
    "generator: lines\n"
    f"families:\n  - {{direction: {ANGLE:.0f}deg, base_spacing: {SPACING // 1000}mm}}\n"
)


def render(tmp_path: Path, definition: str = SLANTED) -> Path:
    path = tmp_path / "out.pdf"
    build(loads(definition, None, source="test"), PdfWriter(str(path)))
    return path


def _perpendicular(line, angle_deg: float = ANGLE) -> float:
    radians = math.radians(angle_deg)
    return -line.x1 * math.sin(radians) + line.y1 * math.cos(radians)


#: The pattern area's origin on the sheet: 20 mm of margin in both directions.
#: The scale is zeroed on it, so the file's numbers are measured from there.
ORIGIN = (20_000, 20_000)


def test_neighbouring_lines_are_the_perpendicular_spacing_apart(tmp_path: Path) -> None:
    radians = math.radians(ANGLE)
    zero = -ORIGIN[0] * math.sin(radians) + ORIGIN[1] * math.cos(radians)
    drawn = sorted(_perpendicular(line) - zero for line in lines_um(render(tmp_path)))
    steps = [b - a for a, b in zip(drawn, drawn[1:], strict=False)]
    assert len(steps) > 30  # the family really fills the sheet
    # A micrometre of tolerance is what integer positions cost (§ 3.3); it does
    # not accumulate, which the next two assertions are there to say.
    assert all(abs(step - SPACING) <= 1 for step in steps)
    assert max(abs(d - round(d / SPACING) * SPACING) for d in drawn) <= 1
    # And line 0 goes through the pattern area's origin — the decision this
    # whole feature turned on, read out of the file.
    assert min(abs(d) for d in drawn) <= 1


def test_the_lines_really_run_at_the_declared_angle(tmp_path: Path) -> None:
    longest = max(
        lines_um(render(tmp_path)),
        key=lambda line: (line.x2 - line.x1) ** 2 + (line.y2 - line.y1) ** 2,
    )
    angle = math.degrees(math.atan2(longest.y2 - longest.y1, longest.x2 - longest.x1)) % 180
    assert angle == pytest.approx(ANGLE, abs=0.001)


def test_nothing_is_drawn_outside_the_pattern_area(tmp_path: Path) -> None:
    # 20 mm margins on A4: the area is 20…190 mm across and 20…277 mm up.
    for line in lines_um(render(tmp_path)):
        for x, y in ((line.x1, line.y1), (line.x2, line.y2)):
            assert 19_999 <= x <= 190_001
            assert 19_999 <= y <= 277_001
