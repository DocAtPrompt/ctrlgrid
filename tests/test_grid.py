"""The `grid` blade (§ 7.4) — count-driven, one block per page.

Everything else in this tool is spacing-driven: you say 5 mm and the sheet
holds as many as it holds. Here you say ten by ten and the *cells* take their
size from the pattern area. § 7.4 allows exactly one block, centred, because
several positioned blocks would be a layout system through the back door.

Cells come out square, and that is what makes "centred" mean anything: the
block takes the smaller of the two possible cell sizes and the leftover is air
around it (§ 8.2 — nothing is stretched to fill).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid.errors import DefinitionError
from ctrlgrid.generators.grid import GridConfig, GridGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Polygon, Segment, Text
from ctrlgrid.pages import PageContext, build
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=100_000, height=80_000)
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")
Q = PdfWriter("unused.pdf")

CELLS = {"cells": {"x": 10, "y": 8}}


def marks(definition: dict, area: Area = AREA) -> list:
    config = GridConfig.model_validate(definition)
    return list(GridGenerator().generate(config, area=area, page=PAGE, q=Q))


def segments(definition: dict, area: Area = AREA) -> list[Segment]:
    return [mark for mark in marks(definition, area) if isinstance(mark, Segment)]


class TestTheBlock:
    def test_the_cells_are_square(self) -> None:
        # 100 x 80 mm for 10 x 8 cells: 10 mm either way, and the block fills
        # this area exactly.
        drawn = segments(CELLS)
        verticals = sorted({s.start.x for s in drawn if s.start.x == s.end.x})
        horizontals = sorted({s.start.y for s in drawn if s.start.y == s.end.y})
        assert verticals[1] - verticals[0] == horizontals[1] - horizontals[0] == 10_000

    def test_a_block_smaller_than_the_area_is_centred(self) -> None:
        # 10 x 4 cells in the same area: the cell size follows the tighter
        # axis (20 mm), so the block is 200 mm — no. It follows the *smaller*
        # of the two, 10 mm, and the 40 mm left over is split.
        drawn = segments({"cells": {"x": 10, "y": 4}})
        verticals = sorted({s.start.x for s in drawn if s.start.x == s.end.x})
        horizontals = sorted({s.start.y for s in drawn if s.start.y == s.end.y})
        assert verticals[0] == 0 and verticals[-1] == 100_000
        assert horizontals[0] == 20_000 and horizontals[-1] == 60_000

    def test_a_line_is_drawn_once_and_not_per_cell(self) -> None:
        # § 7.7 states it for tilings and it holds here: shared edges drawn
        # twice show at low opacity and double the file size.
        drawn = segments(CELLS)
        assert len(drawn) == (10 + 1) + (8 + 1)

    def test_zero_cells_is_a_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            GridConfig.model_validate({"cells": {"x": 0, "y": 4}})


class TestFill:
    def polygons(self, definition: dict) -> list[Polygon]:
        return [mark for mark in marks(definition) if isinstance(mark, Polygon)]

    def test_none_is_the_default(self) -> None:
        assert self.polygons(CELLS) == []

    def test_checker_fills_every_other_cell(self) -> None:
        filled = self.polygons({**CELLS, "fill": "checker"})
        assert len(filled) == 10 * 8 // 2

    def test_rows_fills_every_other_row(self) -> None:
        filled = self.polygons({**CELLS, "fill": "rows"})
        assert len(filled) == 10 * 4

    def test_columns_fills_every_other_column(self) -> None:
        filled = self.polygons({**CELLS, "fill": "columns"})
        assert len(filled) == 5 * 8

    def test_the_fill_colour_is_used(self) -> None:
        filled = self.polygons({**CELLS, "fill": "checker", "fill_color": "#eeeeee"})
        assert {polygon.fill_color for polygon in filled} == {"#eeeeee"}

    def test_the_fill_is_drawn_before_the_lines(self) -> None:
        # § 3.6: the writer does not sort, so the order marks arrive in *is*
        # the stacking — a fill emitted afterwards would cover the grid.
        drawn = marks({**CELLS, "fill": "checker"})
        first_line = next(i for i, m in enumerate(drawn) if isinstance(m, Segment))
        last_fill = max(i for i, m in enumerate(drawn) if isinstance(m, Polygon))
        assert last_fill < first_line


class TestLabels:
    def texts(self, definition: dict) -> list[Text]:
        return [mark for mark in marks(definition) if isinstance(mark, Text)]

    def test_columns_and_rows_take_counting_patterns(self) -> None:
        # § 7.10: "A" gives A … J for ten columns, "n" gives 1 … 8 for rows.
        drawn = self.texts({**CELLS, "labels": {"columns": "A", "rows": "n"}})
        contents = [text.content for text in drawn]
        assert contents[:10] == list("ABCDEFGHIJ")
        assert contents[10:] == [str(number) for number in range(1, 9)]

    def test_column_labels_stand_above_the_block(self) -> None:
        drawn = self.texts({**CELLS, "labels": {"columns": "A"}})
        top = max(s.start.y for s in segments({**CELLS, "labels": {"columns": "A"}}))
        assert all(text.pos.y > top for text in drawn)

    def test_row_labels_stand_left_of_the_block(self) -> None:
        drawn = self.texts({**CELLS, "labels": {"rows": "n"}})
        left = min(s.start.x for s in segments({**CELLS, "labels": {"rows": "n"}}))
        assert all(text.pos.x < left for text in drawn)

    def test_labels_make_room_and_do_not_overlap_the_block(self) -> None:
        # § 8.4's rule in another dress: the label gutter is taken out of the
        # area before the cells are measured, not written over them.
        plain = segments(CELLS)
        labelled = segments({**CELLS, "labels": {"columns": "A", "rows": "n"}})
        assert max(s.start.x for s in labelled) < max(s.start.x for s in plain)

    def test_an_explicit_list_of_the_wrong_length_is_refused(self) -> None:
        config = GridConfig.model_validate({**CELLS, "labels": {"columns": ["N", "O"]}})
        with pytest.raises(DefinitionError) as excinfo:
            GridGenerator().check(config, area=AREA, q=Q)
        message = str(excinfo.value)
        assert "2" in message and "10" in message

    def test_a_label_too_wide_for_its_cell_is_refused(self) -> None:
        config = GridConfig.model_validate(
            {"cells": {"x": 40, "y": 4}, "labels": {"columns": "nnn"},
             "font": {"size": "12pt"}}
        )
        with pytest.raises(DefinitionError) as excinfo:
            GridGenerator().check(config, area=AREA, q=Q)
        assert "cell" in str(excinfo.value)


class TestHeaderRow:
    def test_it_is_off_by_default(self) -> None:
        assert GridConfig.model_validate(CELLS).header_row is False

    def test_it_draws_the_first_row_apart(self) -> None:
        # § 7.4 names the key and nothing else: the top row is marked off by
        # a heavier rule under it, which is what a score sheet needs.
        drawn = segments({**CELLS, "header_row": True, "weight": "0.3pt"})
        horizontals = [s for s in drawn if s.start.y == s.end.y]
        heaviest = max(horizontals, key=lambda s: s.weight)
        assert heaviest.weight > min(s.weight for s in horizontals)
        assert heaviest.start.y == sorted({s.start.y for s in horizontals})[-2]


class TestTheSeam:
    def test_snapping_is_refused_for_a_count_driven_block(self) -> None:
        # § 8.3 lists `grid` among the blades where snapping is an error.
        assert GridGenerator().supports_snap is False

    def test_nothing_is_periodic(self) -> None:
        assert GridGenerator().periodic_axes(GridConfig.model_validate(CELLS)) == {}

    def test_describe_reports_the_cell_count(self) -> None:
        described = "\n".join(GridGenerator().describe(GridConfig.model_validate(CELLS)))
        assert "10" in described and "8" in described


class TestOnTheSheet:
    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a5\n  margin: 10mm\n"
        "generator: grid\n"
        "cells: {x: 10, y: 10}\n"
        "labels:\n  columns: 'A'\n  rows: 'n'\n"
        "fill: checker\n"
        "fill_color: '#eeeeee'\n"
    )

    def test_it_reaches_the_pdf(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "grid.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert pdfread.page_count(path) == 1
        assert "A" in pdfread.text_on(path)

    def test_the_cells_measure_the_same_in_both_directions(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "grid.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        drawn = pdfread.lines_um(path)
        columns = sorted({round(line.x1) for line in drawn if line.is_vertical})
        rows = sorted({round(line.y1) for line in drawn if line.is_horizontal})
        assert columns[1] - columns[0] == pytest.approx(rows[1] - rows[0], abs=2)

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()
