"""`plot-a4`, measured out of its own PDF (§ 8.12, § 8.11).

A plotting sheet is only useful if three things agree: the coordinate cross, the
emphasised grid lines and the scale's zero. They agree here by arithmetic, not
by luck, and the arithmetic is fragile in a way a reader would not guess —

* the pattern area must be an **even multiple of the emphasised period**, or
  its middle falls between two heavy lines;
* the weight cycle must put the heavy line **first** (`[2.4, 1, 1, 1, 1]`), or
  the heavy lines sit at 4, 9, 14 mm from the edge and the middle misses them
  again.

Both were wrong in the first version of this preset, and neither showed in any
test until one was written that read the finished sheet. Hence this file.
"""

from __future__ import annotations

from pathlib import Path

from ctrlgrid.loader import load_preset
from ctrlgrid.pages import build
from ctrlgrid.writers.pdf import PdfWriter
from tests.pdfread import lines_um


def _sheet(tmp_path: Path):
    path = tmp_path / "plot.pdf"
    build(load_preset("plot-a4"), PdfWriter(path))
    return lines_um(path)


def _by_weight(lines):
    """The three kinds of line, told apart by their stroke width: the
    millimetre grid, the emphasised fifth, and the axes."""
    widths = sorted({round(line.width_mm, 4) for line in lines})
    thin, emphasised, axis = widths[0], widths[1], widths[-1]
    return thin, emphasised, axis


def test_the_cross_lies_on_the_emphasised_grid_lines(tmp_path: Path) -> None:
    lines = _sheet(tmp_path)
    verticals = [line for line in lines if line.is_vertical and abs(line.y1 - line.y2) > 100_000]
    horizontals = [
        line for line in lines if line.is_horizontal and abs(line.x1 - line.x2) > 100_000
    ]
    _thin, emphasised, axis = _by_weight(verticals)

    axis_x = [round(line.x1) for line in verticals if round(line.width_mm, 4) == axis]
    axis_y = [round(line.y1) for line in horizontals if round(line.width_mm, 4) == axis]
    heavy_x = {round(line.x1) for line in verticals if round(line.width_mm, 4) == emphasised}
    heavy_y = {round(line.y1) for line in horizontals if round(line.width_mm, 4) == emphasised}

    assert len(axis_x) == 1 and len(axis_y) == 1
    assert axis_x[0] in heavy_x
    assert axis_y[0] in heavy_y


def test_the_scales_zero_is_the_cross(tmp_path: Path) -> None:
    lines = _sheet(tmp_path)
    verticals = [line for line in lines if line.is_vertical and abs(line.y1 - line.y2) > 100_000]
    horizontals = [
        line for line in lines if line.is_horizontal and abs(line.x1 - line.x2) > 100_000
    ]
    _thin, _emphasised, axis = _by_weight(verticals)
    axis_x = [round(line.x1) for line in verticals if round(line.width_mm, 4) == axis][0]
    axis_y = [round(line.y1) for line in horizontals if round(line.width_mm, 4) == axis][0]

    # The ruler's labelled ticks: short lines at the edges, 3 mm long.
    bottom = sorted({round(line.x1) for line in lines if line.is_vertical
                     and 2500 < (line.y1 - line.y2) < 5000})
    left = sorted({round(line.y1) for line in lines if line.is_horizontal
                   and 2500 < (line.x1 - line.x2) < 5000})

    assert (bottom[0] + bottom[-1]) // 2 == axis_x
    assert (left[0] + left[-1]) // 2 == axis_y
    # And every number is a whole 10 mm from the cross — the ladder hangs on
    # the zero, so nothing is half a step out.
    assert all((x - axis_x) % 10_000 == 0 for x in bottom)
    assert all((y - axis_y) % 10_000 == 0 for y in left)
