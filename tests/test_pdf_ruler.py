"""The edge ruler, read back out of a finished PDF (§ 8.12).

A unit test can agree with a bug: it asks the code what it computed. This asks
the *file* — the same way `test_dimensional.py` guards the one promise — and it
is the only check that catches a tick drawn the wrong way or a number that ran
off the sheet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter
from tests.pdfread import lines_um, text_on

RULED = (
    "version: 1\n"
    "page:\n  format: a4\n  margin: 20mm\n"
    "pattern:\n  remainder: end\n"
    "generator: lines\n"
    "families:\n  - {direction: horizontal, base_spacing: 10mm}\n"
    "ruler:\n  edges: [bottom, left]\n  unit: cm\n"
)


def render(tmp_path: Path, definition: str = RULED) -> Path:
    path = tmp_path / "out.pdf"
    build(loads(definition, None, source="test"), PdfWriter(str(path)))
    return path


def test_the_scale_starts_at_the_pattern_origin_and_steps_ten_millimetres(
    tmp_path: Path,
) -> None:
    path = render(tmp_path)
    # The long ticks of the bottom scale: vertical lines hanging below the
    # pattern area's bottom edge (20 mm up from the sheet's edge).
    long_ticks = sorted(
        {
            round(line.x1)
            for line in lines_um(path)
            if line.is_vertical and abs(line.y1 - 20_000) < 1 and line.y1 - line.y2 > 2500
        }
    )
    assert long_ticks[0] == pytest.approx(20_000, abs=1)  # zero on the pattern origin
    assert long_ticks[1] - long_ticks[0] == pytest.approx(10_000, abs=1)
    # 170 mm of pattern width carries eighteen labelled ticks, 0…170 mm.
    assert len(long_ticks) == 18


def test_the_left_scale_zeroes_on_the_same_corner(tmp_path: Path) -> None:
    path = render(tmp_path)
    long_ticks = sorted(
        {
            round(line.y1)
            for line in lines_um(path)
            if line.is_horizontal and abs(line.x1 - 20_000) < 1 and line.x1 - line.x2 > 2500
        }
    )
    assert long_ticks[0] == pytest.approx(20_000, abs=1)
    assert long_ticks[1] - long_ticks[0] == pytest.approx(10_000, abs=1)


def test_the_numbers_are_in_the_file_and_count_centimetres(tmp_path: Path) -> None:
    text = text_on(render(tmp_path))
    for number in ("0", "1", "5", "10", "20"):
        assert number in text


def test_the_ticks_are_the_three_lengths_of_the_ladder(tmp_path: Path) -> None:
    path = render(tmp_path)
    lengths = {
        round(line.y1 - line.y2)
        for line in lines_um(path)
        if line.is_vertical and abs(line.y1 - 20_000) < 1
    }
    assert lengths == {1200, 2000, 3000}
