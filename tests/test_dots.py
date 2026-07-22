"""The `dots` blade (§ 7.2) — two crossed cycles.

A dot grid is the cartesian product of two families, and the only genuinely new
question is what happens where they meet: `combine` answers it explicitly
rather than letting the code guess, and colour is refused outright unless an
axis is named, because `max("#888888", "#cc0000")` means nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ctrlgrid.generators.dots import DotsConfig, DotsGenerator
from ctrlgrid.loader import loads
from ctrlgrid.marks import Area, Dot, Layer
from ctrlgrid.pages import PageContext, build
from ctrlgrid.writers.pdf import PdfWriter

AREA = Area(width=40_000, height=30_000)
PAGE = PageContext(index=0, number=1, count=1, name=None, is_even=False, seed_material=b"")

GRID = {"grid": {"x": {"base_spacing": "10mm"}, "y": {"base_spacing": "10mm"}}}


def dots(definition: dict, area: Area = AREA) -> list[Dot]:
    config = DotsConfig.model_validate(definition)
    return list(DotsGenerator().generate(config, area=area, page=PAGE, q=None))


class TestTheGrid:
    def test_it_is_the_product_of_the_two_families(self) -> None:
        # 40 x 30 mm at 10 mm: five columns, four rows, origin included.
        assert len(dots(GRID)) == 5 * 4

    def test_the_two_axes_are_independent(self) -> None:
        drawn = dots(
            {"grid": {"x": {"base_spacing": "10mm"}, "y": {"base_spacing": "15mm"}}}
        )
        assert len({dot.pos.x for dot in drawn}) == 5
        assert len({dot.pos.y for dot in drawn}) == 3

    def test_the_spacing_cycle_works_as_it_does_everywhere(self) -> None:
        drawn = dots(
            {
                "grid": {
                    "x": {"base_spacing": "10mm", "spacing": [1, 2]},
                    "y": {"base_spacing": "30mm"},
                }
            }
        )
        assert sorted({dot.pos.x for dot in drawn}) == [0, 10_000, 30_000, 40_000]

    def test_everything_is_on_the_pattern_layer(self) -> None:
        assert {dot.layer for dot in dots(GRID)} == {Layer.PATTERN}


class TestCombine:
    """§ 7.2: the question the parser would otherwise have to guess."""

    EMPHASIS = {
        "grid": {"x": {"base_spacing": "10mm"}, "y": {"base_spacing": "10mm"}},
        "base_size": "0.3mm",
        "size_x": [1, 2],
        "size_y": [1, 3],
    }

    def sizes(self, combine: str) -> dict[tuple[int, int], float]:
        drawn = dots({**self.EMPHASIS, "combine": combine})
        return {(dot.pos.x, dot.pos.y): dot.diameter for dot in drawn}

    def test_max_gives_a_cross_grid(self) -> None:
        sizes = self.sizes("max")
        assert sizes[(10_000, 0)] == pytest.approx(0.6)  # emphasised column
        assert sizes[(0, 10_000)] == pytest.approx(0.9)  # emphasised row
        assert sizes[(10_000, 10_000)] == pytest.approx(0.9)  # the larger of the two

    def test_product_makes_the_crossings_largest(self) -> None:
        sizes = self.sizes("product")
        assert sizes[(10_000, 10_000)] == pytest.approx(1.8)

    def test_intersection_only_emphasises_where_both_agree(self) -> None:
        # § 7.2: "only where both cycles are emphasised" — so the smaller of
        # the two decides, and a lone emphasised column stays plain.
        sizes = self.sizes("intersection_only")
        assert sizes[(10_000, 0)] == pytest.approx(0.3)
        assert sizes[(10_000, 10_000)] == pytest.approx(0.6)

    def test_max_is_the_default(self) -> None:
        assert DotsConfig.model_validate(GRID).combine == "max"


class TestColour:
    def test_one_colour_applies_to_every_dot(self) -> None:
        drawn = dots({**GRID, "color": "#888888"})
        assert {dot.color for dot in drawn} == {"#888888"}

    def test_a_cycle_without_an_axis_is_a_validation_error(self) -> None:
        # § 7.2: an explicit error, never a guessed default — any mixing rule
        # between the two axes would be invented.
        with pytest.raises(ValidationError) as excinfo:
            DotsConfig.model_validate({**GRID, "color": ["#111111", "#222222"]})
        assert "axis" in str(excinfo.value)

    def test_axis_x_gives_colour_stripes_down_the_columns(self) -> None:
        drawn = dots(
            {**GRID, "color": {"axis": "x", "cycle": ["#111111", "#222222"]}}
        )
        by_column = {dot.pos.x: dot.color for dot in drawn}
        assert by_column[0] == "#111111"
        assert by_column[10_000] == "#222222"

    def test_axis_y_stripes_the_rows_instead(self) -> None:
        drawn = dots(
            {**GRID, "color": {"axis": "y", "cycle": ["#111111", "#222222"]}}
        )
        by_row = {dot.pos.y: dot.color for dot in drawn}
        assert by_row[0] == "#111111"
        assert by_row[10_000] == "#222222"

    def test_cross_takes_the_accent_when_either_axis_is_at_it(self) -> None:
        # The colour counterpart of `combine: max`: the later entry of the
        # cycle is the accent, and a coloured cross-grid needs it as soon as
        # the column *or* the row stands on it.
        drawn = dots(
            {**GRID, "color": {"axis": "cross", "cycle": ["#111111", "#cc0000"]}}
        )
        colors = {(dot.pos.x, dot.pos.y): dot.color for dot in drawn}
        assert colors[(0, 0)] == "#111111"
        assert colors[(10_000, 0)] == "#cc0000"
        assert colors[(0, 10_000)] == "#cc0000"

    def test_an_axis_without_a_cycle_is_an_error(self) -> None:
        with pytest.raises(ValidationError):
            DotsConfig.model_validate({**GRID, "color": {"axis": "x"}})


class TestTheSeam:
    def test_both_axes_are_periodic(self) -> None:
        # § 8.3: unlike `polar`, a dot grid snaps — it has two axes.
        axes = DotsGenerator().periodic_axes(DotsConfig.model_validate(GRID))
        assert set(axes) == {"x", "y"}
        assert axes["x"][0].step_um == 10_000

    def test_snapping_is_supported(self) -> None:
        assert DotsGenerator().supports_snap is True

    def test_describe_reports_both_axes(self) -> None:
        described = "\n".join(DotsGenerator().describe(DotsConfig.model_validate(GRID)))
        assert described.count("10mm") == 2

    def test_the_pattern_is_the_same_on_every_page(self) -> None:
        assert DotsGenerator().is_page_invariant(DotsConfig.model_validate(GRID)) is True


class TestOnTheSheet:
    DEFINITION = (
        "version: 1\n"
        "page:\n  format: a6\n  margin: 5mm\n"
        "generator: dots\n"
        "grid:\n"
        "  x: {base_spacing: 5mm}\n"
        "  y: {base_spacing: 5mm}\n"
        "base_size: 0.3mm\n"
        "size_x: [1, 1, 1, 1, 2]\n"
        "size_y: [1, 1, 1, 1, 2]\n"
        "color: '#888888'\n"
    )

    def test_it_reaches_the_pdf(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "dots.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert pdfread.page_count(path) == 1

    def test_a_dot_is_a_zero_length_stroke(self, tmp_path: Path) -> None:
        # § 10.1: 2500 dots as four Bézier curves each is the difference
        # between a small file and a double-digit megabyte one.
        import pdfread

        path = tmp_path / "dots.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        drawn = pdfread.lines_um(path)
        assert drawn
        assert all(
            abs(line.x1 - line.x2) < 1 and abs(line.y1 - line.y2) < 1 for line in drawn
        )

    def test_the_spacing_measures_five_millimetres(self, tmp_path: Path) -> None:
        import pdfread

        path = tmp_path / "dots.pdf"
        build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        columns = sorted({round(line.x1) for line in pdfread.lines_um(path)})
        steps = {columns[index + 1] - columns[index] for index in range(len(columns) - 1)}
        assert steps == {5000}

    def test_two_runs_produce_identical_bytes(self, tmp_path: Path) -> None:
        first, second = tmp_path / "a.pdf", tmp_path / "b.pdf"
        for path in (first, second):
            build(loads(self.DEFINITION, source="test"), PdfWriter(path))
        assert first.read_bytes() == second.read_bytes()
