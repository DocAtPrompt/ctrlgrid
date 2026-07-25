"""A net, measured out of a finished PDF (§ 7.14, § 8.2).

This is the generator whose whole point is millimetre accuracy — a box 2 mm out
does not close — so the numbers are read back out of the written file rather
than out of the code that wrote it.

What no test can do is cut the sheet out and fold it. That check belongs to a
human with scissors, and the specification says so.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctrlgrid.loader import loads
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter
from tests.pdfread import lines_um

TRAY = (
    "version: 1\n"
    "page: {format: a4, margin: 10mm}\n"
    "generator: net\nstyle: tray\n"
    "length: 80mm\nwidth: 50mm\nheight: 30mm\n"
)


def render(tmp_path: Path, definition: str = TRAY) -> Path:
    path = tmp_path / "net.pdf"
    build(loads(definition, None, source="test"), PdfWriter(path))
    return path


def test_the_base_measures_its_inner_size_out_of_the_file(tmp_path: Path) -> None:
    drawn = lines_um(render(tmp_path))
    # The base's four creases are the only dashed lines of a tray, and they
    # bound exactly the inner size the definition asked for.
    creases = [line for line in drawn if line.width_mm < 0.1]
    xs = sorted({round(line.x1) for line in creases if line.is_vertical})
    ys = sorted({round(line.y1) for line in creases if line.is_horizontal})
    assert xs[-1] - xs[0] == pytest.approx(80_000, abs=1)
    assert ys[-1] - ys[0] == pytest.approx(50_000, abs=1)


def test_the_whole_net_stays_inside_the_pattern_area(tmp_path: Path) -> None:
    # A4 with a 10 mm margin: 10…200 mm across, 10…287 mm up.
    for line in lines_um(render(tmp_path)):
        for x, y in ((line.x1, line.y1), (line.x2, line.y2)):
            assert 9_999 <= x <= 200_001
            assert 9_999 <= y <= 287_001


def test_the_net_is_centred_on_the_sheet(tmp_path: Path) -> None:
    drawn = lines_um(render(tmp_path))
    xs = [value for line in drawn for value in (line.x1, line.x2)]
    ys = [value for line in drawn for value in (line.y1, line.y2)]
    # 210 x 297 mm sheet: the net's own middle is the sheet's middle.
    assert (min(xs) + max(xs)) / 2 == pytest.approx(105_000, abs=500)
    assert (min(ys) + max(ys)) / 2 == pytest.approx(148_500, abs=500)


def test_no_line_is_drawn_twice(tmp_path: Path) -> None:
    # An edge is a cut *or* a crease, never both: two strokes on one line would
    # print as a heavier line and cut where the knife should not go.
    drawn = lines_um(render(tmp_path))
    keys = [
        tuple(sorted(((round(line.x1), round(line.y1)), (round(line.x2), round(line.y2)))))
        for line in drawn
    ]
    assert len(keys) == len(set(keys))


def test_two_runs_produce_identical_bytes(tmp_path: Path) -> None:
    first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
    build(loads(TRAY, None, source="test"), PdfWriter(first))
    build(loads(TRAY, None, source="test"), PdfWriter(second))
    assert first.read_bytes() == second.read_bytes()
